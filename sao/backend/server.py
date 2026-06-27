import grpc
import sys
import os
from concurrent import futures
import flatbuffers
import asyncio

from sao.ipc.sao_grpc_fb import SaoServiceServicer, add_SaoServiceServicer_to_server
from sao.ipc import ChatRequest, ChatResponse
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
        async for chunk in self.router.generate_response_stream(model_id, messages, self.mcp.get_tool_schemas()):
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

    def ChatStream(self, request, context):
        # We must bridge sync generator to async logic
        # In grpcio 1.64+, you can run an async servicer, but standard is sync.
        # Let's use asyncio.run or context logic. Wait, grpc has an async server api.
        # But our servicer inherits from standard (which can be async in new grpcio).
        # We'll just run an event loop for the generator.
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async_gen = self._async_chat_stream(request, context)
        
        try:
            while True:
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
        except StopAsyncIteration:
            pass
        finally:
            loop.run_until_complete(async_gen.aclose())
            loop.close()


async def serve_async():
    server = grpc.aio.server()
    db = Database()
    await db.init_db()
    
    add_SaoServiceServicer_to_server(SaoServicer(db, Router(), MCPManager()), server)
    server.add_insecure_port('[::]:50051')
    await server.start()
    print("Backend AI Core started on port 50051")
    await server.wait_for_termination()

def serve():
    asyncio.run(serve_async())

if __name__ == '__main__':
    serve()
