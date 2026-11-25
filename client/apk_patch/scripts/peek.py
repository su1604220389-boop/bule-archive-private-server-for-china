import zipfile, json
BASE=r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot\BA_noroot_prod_20261118_v1.apk'
z=zipfile.ZipFile(BASE)
names=[n for n in z.namelist() if '__tpinfo' in n]
print('tpinfo entries present:', names if names else 'NONE (already removed)')
d=z.read('assets/SDKConfigSettings.json').decode('utf-8-sig')
print('--- SDKConfigSettings.json ---')
print(d)
