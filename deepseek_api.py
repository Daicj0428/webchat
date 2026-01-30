from openai import OpenAI

def deepseek1(message, stream=True):
    client = OpenAI(
     base_url="https://api.deepseek.com/",
    #  api_key="sk-7eff2b5783d042a096ebe4792bec898d"
    #  api_key="sk-afff8a14b2e6437eb4f9bef2d7dac989"
     api_key="sk-f0c57962405e4e0e8bfce0b557828123"
     #腾讯云
     # base_url="https://api.lkeap.cloud.tencent.com/v1",
     # api_key="sk-8oIweRnma6fDLmFcwuRwyJP01Z91sBCTVehzHWMNdSvNdsSx"
     # api_key="sk-vKrwYlZEq8OqbXXbVFF1dLLiM4ywmRIZv9Oc5JsPkGNWHZXU"


    )
    completion = client.chat.completions.create(
        # deepseek官方 DeepSeek-V3-0324 - 推荐
        model="deepseek-chat",
        # deepseek官方 DeepSeek-R1-0528 - 推理模型
        # model="deepseek-reasoner",
        # 腾讯云
        # model="deepseek-v3",
        messages=message,
        stream=stream

    )
    if stream:
        # 返回生成器对象
        for chunk in completion:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    else:
        return completion.choices[0].message.content    

    # print(completion.choices[0].message.content)
    # return completion.choices[0].message.content