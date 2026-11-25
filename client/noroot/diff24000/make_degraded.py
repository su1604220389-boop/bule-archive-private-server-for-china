import json,sys,base64,hashlib
sys.path.insert(0,r"work\ba\server\deploy")
import gen24000 as G
tok=base64.b64encode(hashlib.sha384(b"ba24000:0").digest()).decode()
obj0=G.b24000_build(0,tok,'00000000-0000-4000-8000-000000000000',639304064280547870)
out=r"work\ba\noroot\diff24000\our_degraded_account0.json"
with open(out,'w',encoding='utf-8',newline='\n') as fh:
    json.dump(obj0,fh,ensure_ascii=False,indent=1); fh.write('\n')
print("degraded aid=0 token_len=",len(obj0['SessionKey']['MxToken']), "loc0.AccountId=",obj0['AcademyLocationDBs'][0]['AccountId'])
