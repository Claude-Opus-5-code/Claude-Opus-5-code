import requests

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en',
    'authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjozODg4OTczMzM0OTg3Mzg4NzMsImlhdCI6MTc4OTA0NjM5NSwiZXhwIjoxNzkxNjM4Mzk1fQ.BoarBuC8sESh5789x4tSQaGdHs3VjWlW4UQFKj78QhU',
    'origin': 'https://syntx.ai',
    'priority': 'u=1, i',
    'referer': 'https://syntx.ai/',
    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
}

params = {
    'enabled_only': 'true',
    'lang': 'en',
}

response = requests.get('https://api.syntx.ai/api/v1/llm/models', params=params, headers=headers)

all_models_li = response.json()
#print(all_models_li)
free_mode_li = []
all_li = []
for mod in all_models_li['models']:
    li_dd =mod["available_subscriptions"]
    print(li_dd)
    if li_dd ==[]:
     free_mode_li.append(mod["ai_name"])
     free_mode_li.append(mod["label"])
     free_mode_li.append(mod["id"])
     free_mode_li.append(mod["capabilities"])

    #all_li.append(mod["id"])
print(free_mode_li)
# الصور 
# #بيستت
# ً÷ـيخهتب
# الانشاء 
# التجيل 
# الريفريش 
# الاثت
#    الشاات جايبه داله التسجيل لومفيش حسابت طيب لوفي هبعت عليطو طيبلومنتهي تجديد وابعت المهم هترجليعي رداا كان الي مطلوب نفس الكلام بالنسبه لباقي الدول الصور الو الصوت او اي capabiletis متاحه المهم تكون مهندله ذاتيا
def register(session ,timeout= 120):
    # TODO: handle registration ==.json
    pass
    
def refrish(email):
    #refrish
    pass
def ask(model,mode =planinign , role,prompt,timeout= 120):
    #ask (ops,img ,video,chat)
    # if acount ===>done
    #