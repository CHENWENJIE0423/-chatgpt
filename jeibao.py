import json
import os
import pprint
from typing import List, Dict
import dotenv
from httpx import AsyncClient
from collections import defaultdict
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
dotenv.load_dotenv()

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def request(val: List[Dict[str, str]]):
    url = "https://api.zhizengzeng.com/v1/chat/completions"
    model = "gpt-3.5-turbo"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('API_KEY')}",
    }
    params = {
        "model": model,
        "messages": val,
        "temperature": 0.8,
        "n": 1,
        "max_tokens": 3000,
        "stream": True
    }

    async with AsyncClient() as client:
        async with client.stream("POST", url, headers=headers, json=params, timeout=60) as response:
            async for line in response.aiter_lines():
                if line.strip() == "":
                    continue
                if line.strip() == "[DONE]":
                    break
                try:
                    line = line.replace("data: ", "")
                    data = json.loads(line)
                    if data.get("choices") is None or len(data.get("choices")) == 0 or data.get("choices")[0].get(
                            "finish_reason") is not None:
                        return
                    yield data.get("choices")[0]
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e} with line: {line}")


@app.websocket("/chat")
async def chat(websocket: WebSocket):
    await websocket.accept()  # 确认 WebSocket 连接
    message = []

    while True:
        try:
            data = await websocket.receive_text()
            print(f"Received data: {data}")
            if data == "quit":
                await websocket.close()
                break

            # 添加用户消息
            message.append({"role": "user", "content": str(data)})
            chat_msg = defaultdict(str)

            # 生成并发送 AI 回复
            async for i in request(message):
                # 只提取角色和内容，忽略 logprobs
                if i.get("delta"):
                    if "role" in i["delta"]:
                        chat_msg["role"] = i["delta"]["role"]
                    if "content" in i["delta"]:
                        chat_msg["content"] += i["delta"]["content"]
                        await websocket.send_text(i["delta"]["content"])

            # 将 AI 的完整回复添加到对话上下文
            message.append(chat_msg)

        except Exception as e:
            print(f"WebSocket connection error: {e}")
            break


if __name__ == '__main__':
    import uvicorn
    uvicorn.run("jeibao:app", host="0.0.0.0", port=8080, reload=True)