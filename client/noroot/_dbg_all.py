import struct
d=open(r"work\ba\audit\ba-apk\AndroidManifest.xml","rb").read()
t,hs,total=struct.unpack_from("<HHI",d,0)
strings=[];resmap=[]
def pool(d,off):
    t2,hs2,sz=struct.unpack_from("<HHI",d,off)
    cnt,stc,flags,sst,sts=struct.unpack_from("<IIIII",d,off+8)
    utf8=bool(flags&0x100); ob=off+hs2; db=off+sst; out=[]
    for i in range(cnt):
        o=struct.unpack_from("<I",d,ob+4*i)[0]; p=db+o
        if utf8:
            n1=d[p]; p+=1
            if n1&0x80: n1=((n1&0x7f)<<8)|d[p]; p+=1
            n2=d[p]; p+=1
            if n2&0x80: n2=((n2&0x7f)<<8)|d[p]; p+=1
            s=d[p:p+n2].decode("utf-8","replace")
        else:
            n=struct.unpack_from("<H",d,p)[0]; p+=2
            s=d[p:p+n*2].decode("utf-16-le","replace")
        out.append(s)
    return out,utf8
pos=hs; nel=0
while pos+8<=len(d):
    ct,chs,csz=struct.unpack_from("<HHI",d,pos)
    if csz<8: break
    if ct==1:
        strings,utf8=pool(d,pos); print("pool",len(strings),"utf8",utf8)
    elif ct==0x180:
        n=(csz-chs)//4; resmap=list(struct.unpack_from("<%dI"%n,d,pos+chs))
    elif ct==0x102:
        nel+=1
        line,cm,ns,name,astart,asize,acount,aidx=struct.unpack_from("<IIIIHHHH",d,pos+chs)
        tag=strings[name] if name<len(strings) else "?"
        out=[]
        for i in range(acount):
            a=pos+chs+astart+i*asize
            ans,anm,araw=struct.unpack_from("<III",d,a)
            asz,res0,atype,adata=struct.unpack_from("<HBBI",d,a+12)
            aname=strings[anm] if anm<len(strings) else "?"
            if (not aname) and anm<len(resmap): aname="@0x%08x"%resmap[anm]
            if atype==3: val=strings[adata] if adata<len(strings) else "?"
            elif atype==0x10: val=str(adata)
            elif atype==0x11: val="0x%x"%adata
            elif atype==0x12: val="true" if adata else "false"
            elif atype==1: val="@ref/0x%08x"%adata
            elif atype==0: val="(null)"
            else: val="(t0x%02x:0x%x)"%(atype,adata)
            out.append((aname,val))
        print("<%s> %s"%(tag, "; ".join("%s=%s"%(k,v) for k,v in out)))
    pos+=csz
print("elements:",nel)
