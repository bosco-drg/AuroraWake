import re, os
LIBDIR='/usr/share/kicad/symbols'
def tokenize(s):
    i=0;n=len(s)
    while i<n:
        c=s[i]
        if c in '()': yield c; i+=1
        elif c.isspace(): i+=1
        elif c=='"':
            j=i+1; buf=[]
            while s[j]!='"':
                if s[j]=='\\': buf.append(s[j+1]); j+=2
                else: buf.append(s[j]); j+=1
            yield ('S',''.join(buf)); i=j+1
        else:
            j=i
            while j<n and not s[j].isspace() and s[j] not in '()': j+=1
            yield s[i:j]; i=j
def parse(s):
    stack=[[]]
    for t in tokenize(s):
        if t=='(': stack.append([])
        elif t==')': x=stack.pop(); stack[-1].append(x)
        else: stack[-1].append(t)
    return stack[0][0]
def q(s): return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'
def dump(x,ind=0):
    if isinstance(x,tuple): return q(x[1])
    if isinstance(x,str): return x
    # list
    parts=[dump(e,ind+1) for e in x]
    simple=all(not isinstance(e,list) for e in x)
    if simple: return '('+' '.join(parts)+')'
    out='('+parts[0]
    for e,p in zip(x[1:],parts[1:]):
        if isinstance(e,list): out+='\n'+'\t'*(ind+1)+p
        else: out+=' '+p
    return out+'\n'+'\t'*ind+')'
def val(x): return x[1] if isinstance(x,tuple) else x
_cache={}
def load_lib(lib):
    if lib not in _cache:
        tree=parse(open(f'{LIBDIR}/{lib}.kicad_sym').read())
        _cache[lib]={val(e[1]):e for e in tree if isinstance(e,list) and e[0]=='symbol'}
    return _cache[lib]
def get_symbol(libid):
    """Return flattened symbol tree with name libid (Lib:Name)."""
    lib,name=libid.split(':',1)
    syms=load_lib(lib)
    s=syms[name]
    ext=[e for e in s if isinstance(e,list) and e[0]=='extends']
    if ext:
        parent=get_symbol(f'{lib}:{val(ext[0][1])}')
        pname=lib+':'+val(ext[0][1]); pshort=val(ext[0][1])
        childprops={val(e[1]):e for e in s if isinstance(e,list) and e[0]=='property'}
        new=['symbol',('S',libid)]
        for e in parent[2:]:
            if isinstance(e,list) and e[0]=='property' and val(e[1]) in childprops:
                new.append(childprops.pop(val(e[1])))
            elif isinstance(e,list) and e[0]=='symbol':
                sub=list(e); sub[1]=('S',val(e[1]).replace(pshort,name,1)); new.append(sub)
            else: new.append(e)
        # insert remaining child props after other props
        idx=max(i for i,e in enumerate(new) if isinstance(e,list) and e[0]=='property')
        for p in childprops.values(): idx+=1; new.insert(idx,p)
        return new
    s=list(s); s[1]=('S',libid); return s
def pins(sym, unit=1):
    """list of dict(number,name,x,y,angle,type) for given unit (incl. unit 0)."""
    res=[]
    for e in sym:
        if isinstance(e,list) and e[0]=='symbol':
            m=re.match(r'.*_(\d+)_(\d+)$',val(e[1]))
            u=int(m.group(1))
            if u not in (0,unit): continue
            for p in e:
                if isinstance(p,list) and p[0]=='pin':
                    at=[x for x in p if isinstance(x,list) and x[0]=='at'][0]
                    nm=[x for x in p if isinstance(x,list) and x[0]=='name'][0]
                    nu=[x for x in p if isinstance(x,list) and x[0]=='number'][0]
                    hidden = any(x=='hide' for x in p) or any(isinstance(x,list) and x[0]=='hide' and len(x)>1 and x[1]=='yes' for x in p)
                    res.append(dict(type=p[1],x=float(at[1]),y=float(at[2]),a=int(float(at[3])) if len(at)>3 else 0,name=val(nm[1]),num=val(nu[1]),hidden=hidden))
    return res
def prop(sym,key):
    for e in sym:
        if isinstance(e,list) and e[0]=='property' and val(e[1])==key: return val(e[2])
