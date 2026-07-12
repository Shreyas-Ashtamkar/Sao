import grpc
import sys
import os
import flatbuffers
import uuid

from sao.ipc.sao_grpc_fb import SaoServiceStub
from sao.ipc import ChatRequest, ChatMessage, ChatResponse, ListModelsRequest, ListModelsResponse, Role

class SaoClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = SaoServiceStub(self.channel)

    def _wait_for_ready(self, timeout=10):
        try:
            grpc.channel_ready_future(self.channel).result(timeout=timeout)
        except grpc.FutureTimeoutError:
            raise RuntimeError("Could not connect to backend server. It may still be starting up.")

    def send_chat_stream(self, session_id, model_id, messages_history, provider="", api_base="", api_key=""):
        self._wait_for_ready()
        builder = flatbuffers.Builder(1024)
        
        # Serialize messages
        msg_offsets = []
        for msg in messages_history:
            content_off = builder.CreateString(msg["content"])
            ChatMessage.Start(builder)
            role_val = 0 # User
            if msg["role"] == "assistant": role_val = 1
            elif msg["role"] == "system": role_val = 2
            elif msg["role"] == "tool": role_val = 3
            ChatMessage.AddRole(builder, role_val)
            ChatMessage.AddContent(builder, content_off)
            msg_offsets.append(ChatMessage.End(builder))
            
        ChatRequest.StartMessagesVector(builder, len(msg_offsets))
        for off in reversed(msg_offsets):
            builder.PrependUOffsetTRelative(off)
        msgs_vec = builder.EndVector()
        
        session_id_off = builder.CreateString(session_id)
        model_id_off = builder.CreateString(model_id)
        provider_off = builder.CreateString(provider)
        api_base_off = builder.CreateString(api_base)
        api_key_off = builder.CreateString(api_key)
        
        ChatRequest.Start(builder)
        ChatRequest.AddSessionId(builder, session_id_off)
        ChatRequest.AddModelId(builder, model_id_off)
        ChatRequest.AddMessages(builder, msgs_vec)
        ChatRequest.AddProvider(builder, provider_off)
        ChatRequest.AddApiBase(builder, api_base_off)
        ChatRequest.AddApiKey(builder, api_key_off)
        
        req = ChatRequest.End(builder)
        builder.Finish(req)
        
        req_bytes = bytes(builder.Output())
        
        # Call streaming gRPC
        response_iterator = self.stub.ChatStream(req_bytes)
        
        for res_bytes in response_iterator:
            res = ChatResponse.ChatResponse.GetRootAs(res_bytes, 0)
            chunk = res.Chunk().decode('utf-8') if res.Chunk() else ""
            is_final = res.IsFinal()
            yield chunk, is_final

    def list_models(self, provider, api_base="", api_key=""):
        self._wait_for_ready()
        builder = flatbuffers.Builder(256)
        provider_off = builder.CreateString(provider)
        api_base_off = builder.CreateString(api_base)
        api_key_off = builder.CreateString(api_key)

        ListModelsRequest.Start(builder)
        ListModelsRequest.AddProvider(builder, provider_off)
        ListModelsRequest.AddApiBase(builder, api_base_off)
        ListModelsRequest.AddApiKey(builder, api_key_off)
        req = ListModelsRequest.End(builder)
        builder.Finish(req)

        response_bytes = self.stub.ListModels(bytes(builder.Output()))
        response = ListModelsResponse.ListModelsResponse.GetRootAs(response_bytes, 0)
        models = [response.Models(i).decode('utf-8') for i in range(response.ModelsLength())]
        error = response.Error().decode('utf-8') if response.Error() else ""
        if error and not models:
            raise RuntimeError(error)

        return models
