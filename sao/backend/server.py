import grpc
from concurrent import futures
import flatbuffers
import asyncio
import signal
from contextlib import suppress

from sao.ipc.sao_grpc_fb import SaoServiceServicer, add_SaoServiceServicer_to_server
from sao.ipc import ChatRequest, ChatResponse, ListModelsRequest, ListModelsResponse
from .router import Router
from .database import Database
from .mcp_manager import MCPManager

class SaoServicer(SaoServiceServicer):
    def __init__(self, db: Database, router: Router, mcp: MCPManager):
        self.db = db
        self.router = router
        self.mcp = mcp

    async def _async_chat_stream(self, request_bytes, context):
        # We assume request_bytes is the raw flatbuffer bytes since flatbuffers gRPC python extension
        # doesn't auto-deserialize objects if not configured with the type, wait, the stub expects objects?
        # Actually in grpc python with flatbuffers, the request is often just bytes, we need to deserialize.
        
        # Let's decode it:
        req = ChatRequest.ChatRequest.GetRootAs(request_bytes, 0)
        session_id = req.SessionId().decode('utf-8')
        model_id = req.ModelId().decode('utf-8')
        provider = req.Provider().decode('utf-8') if req.Provider() else ""
        
        messages = []
        for i in range(req.MessagesLength()):
            msg = req.Messages(i)
            role_enum = msg.Role()
            role_str = "user" if role_enum == 0 else "assistant" if role_enum == 1 else "system" if role_enum == 2 else "tool"
            messages.append({"role": role_str, "content": msg.Content().decode('utf-8')})
            # Also save to db if it's the last message (user message)
            if i == req.MessagesLength() - 1:
                await self.db.add_message(session_id, role_str, messages[-1]["content"])

        # Call the router
        full_response = ""
        async for chunk in self.router.generate_response_stream(
            model_id,
            messages,
            self.mcp.get_tool_schemas(),
            provider=provider,
            tool_executor=self.mcp.execute_tool,
        ):
            # Handle LiteLLM chunk
            if isinstance(chunk, dict) and "error" in chunk:
                content = f"Error: {chunk['error']}"
            elif hasattr(chunk, "choices") and chunk.choices and hasattr(chunk.choices[0], "delta"):
                content = chunk.choices[0].delta.content or ""
            elif isinstance(chunk, dict) and "choices" in chunk:
                content = chunk["choices"][0].get("delta", {}).get("content", "")
            else:
                content = ""
            if content:
                full_response += content
                builder = flatbuffers.Builder(1024)
                session_id_off = builder.CreateString(session_id)
                chunk_off = builder.CreateString(content)
                
                ChatResponse.Start(builder)
                ChatResponse.AddSessionId(builder, session_id_off)
                ChatResponse.AddChunk(builder, chunk_off)
                ChatResponse.AddIsFinal(builder, False)
                res = ChatResponse.End(builder)
                builder.Finish(res)
                
                yield bytes(builder.Output())
                
        # Save assistant message to DB
        await self.db.add_message(session_id, "assistant", full_response, model_used=model_id)

        # Send final chunk
        builder = flatbuffers.Builder(1024)
        session_id_off = builder.CreateString(session_id)
        chunk_off = builder.CreateString("")
        ChatResponse.Start(builder)
        ChatResponse.AddSessionId(builder, session_id_off)
        ChatResponse.AddChunk(builder, chunk_off)
        ChatResponse.AddIsFinal(builder, True)
        res = ChatResponse.End(builder)
        builder.Finish(res)
        yield bytes(builder.Output())

    async def ChatStream(self, request, context):
        async for chunk in self._async_chat_stream(request, context):
            yield chunk

    async def _async_list_models(self, request):
        req = ListModelsRequest.ListModelsRequest.GetRootAs(request, 0)
        provider = req.Provider().decode('utf-8') if req.Provider() else ""

        error = ""
        try:
            discovery = await asyncio.to_thread(self.router.list_available_models, provider)
            if discovery.is_live:
                models = discovery.models
                await self.db.save_provider_models(provider, models)
            else:
                cached_models = await self.db.get_provider_models(provider)
                models = cached_models or self.router.get_static_models(provider)
        except Exception as exc:
            try:
                cached_models = await self.db.get_provider_models(provider)
            except Exception as cache_exc:
                models = []
                error = f"{exc}; cache lookup failed: {cache_exc}"
            else:
                if cached_models:
                    models = cached_models
                else:
                    try:
                        models = self.router.get_static_models(provider)
                    except Exception:
                        models = []
                        error = str(exc)
                if not models:
                    error = str(exc)

        builder = flatbuffers.Builder(1024)
        provider_off = builder.CreateString(provider)
        error_off = builder.CreateString(error)

        model_offsets = [builder.CreateString(model) for model in models]
        models_vec = 0
        if model_offsets:
            ListModelsResponse.ListModelsResponseStartModelsVector(builder, len(model_offsets))
            for model_offset in reversed(model_offsets):
                builder.PrependUOffsetTRelative(model_offset)
            models_vec = builder.EndVector()

        ListModelsResponse.ListModelsResponseStart(builder)
        ListModelsResponse.ListModelsResponseAddProvider(builder, provider_off)
        if models_vec:
            ListModelsResponse.ListModelsResponseAddModels(builder, models_vec)
        ListModelsResponse.ListModelsResponseAddError(builder, error_off)
        res = ListModelsResponse.ListModelsResponseEnd(builder)
        builder.Finish(res)
        return bytes(builder.Output())

    async def ListModels(self, request, context):
        return await self._async_list_models(request)


async def serve_async(shutdown_requested=None):
    server = grpc.aio.server()
    db = Database()
    await db.init_db()
    mcp = MCPManager()
    started = False
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    registered_signals = []
    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(shutdown_signal, shutdown_event.set)
            registered_signals.append(shutdown_signal)
        except NotImplementedError:
            pass

    async def wait_for_shutdown():
        if shutdown_requested is None:
            await shutdown_event.wait()
            return
        while not shutdown_requested.is_set():
            await asyncio.sleep(0.1)

    try:
        startup_task = asyncio.create_task(mcp.connect_servers())
        shutdown_task = asyncio.create_task(wait_for_shutdown())
        done, _ = await asyncio.wait(
            {startup_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if shutdown_task in done:
            startup_task.cancel()
            with suppress(asyncio.CancelledError):
                await startup_task
            return

        await startup_task
        shutdown_task.cancel()
        with suppress(asyncio.CancelledError):
            await shutdown_task
    except (ValueError, OSError, asyncio.TimeoutError) as exc:
        shutdown_task.cancel()
        with suppress(asyncio.CancelledError):
            await shutdown_task
        print(f"MCP initialization failed; continuing without MCP tools: {exc}")

    try:
        add_SaoServiceServicer_to_server(SaoServicer(db, Router(), mcp), server)
        server.add_insecure_port('[::]:50051')
        await server.start()
        started = True
        print("Backend AI Core started on port 50051")
        await wait_for_shutdown()
    finally:
        if started:
            await server.stop(grace=5)
        await mcp.close()
        for shutdown_signal in registered_signals:
            loop.remove_signal_handler(shutdown_signal)

def serve(shutdown_requested=None):
    asyncio.run(serve_async(shutdown_requested))

if __name__ == '__main__':
    serve()
