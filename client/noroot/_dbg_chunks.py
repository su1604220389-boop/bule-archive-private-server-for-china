import struct
d=open(r"work\ba\audit\ba-apk\AndroidManifest.xml","rb").read()
t,hs,total=struct.unpack_from("<HHI",d,0)
pos=hs
n=0
while pos+8<=len(d) and n<12:
    ct,chs,csz=struct.unpack_from("<HHI",d,pos)
    print("chunk type=0x%04x hs=%d sz=%d pos=%d"%(ct,chs,csz,pos))
    if csz<8: break
    pos+=csz; n+=1
