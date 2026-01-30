from openai import OpenAI

def deepseek1(message, stream=True):
    client = OpenAI(
     base_url="https://api.deepseek.com/",
     api_key="sk-xxxxxx"
     #腾讯云
     # base_url="https://api.lkeap.cloud.tencent.com/v1",
     # api_key="sk-xxxxxx"


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
