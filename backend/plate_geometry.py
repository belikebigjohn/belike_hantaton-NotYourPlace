"""Large plate proposals independent of the vehicle-domain neural detector."""
import cv2
import numpy as np

def plate_border_proposals(image):
    height,width=image.shape[:2]
    if min(height,width)<48: return []
    scale=min(1,960/max(height,width))
    sample=cv2.resize(image,(round(width*scale),round(height*scale))) if scale<1 else image
    ih,iw=sample.shape[:2]
    if min(ih,iw)<48: return []
    gray=cv2.cvtColor(sample,cv2.COLOR_BGR2GRAY)
    raw=cv2.HoughLinesP(cv2.Canny(gray,40,130),1,np.pi/180,
        threshold=max(20,int(iw*.1)),minLineLength=iw*.22,maxLineGap=iw*.04)
    if raw is None: return []
    groups=[]
    for x1,y1,x2,y2 in np.asarray(raw).reshape(-1,4):
        if x2<x1: x1,x2,y1,y2=x2,x1,y2,y1
        if x2==x1 or abs((y2-y1)/(x2-x1))>.17: continue
        slope=(y2-y1)/(x2-x1);intercept=y1-slope*x1;center=slope*iw/2+intercept
        group=next((g for g in groups if abs(g['center']-center)<ih*.025 and abs(g['slope']-slope)<.09),None)
        if group:
            group['left']=min(group['left'],x1);group['right']=max(group['right'],x2)
        else: groups.append(dict(left=x1,right=x2,slope=slope,intercept=intercept,center=center))
    proposals=[]
    for top in groups:
        for bottom in groups:
            left=min(top['left'],bottom['left']);right=max(top['right'],bottom['right'])
            w=right-left;gap=bottom['center']-top['center']
            if gap<15 or not 2.8<w/gap<6.5 or abs(top['slope']-bottom['slope'])>.12: continue
            support=((top['right']-top['left'])+(bottom['right']-bottom['left']))/w
            if support<1.2: continue
            y=max(0,int(min(top['slope']*left+top['intercept'],top['slope']*right+top['intercept']))-2)
            lower=min(ih,int(max(bottom['slope']*left+bottom['intercept'],bottom['slope']*right+bottom['intercept']))+3)
            box=(max(0,int(left)-2),y,min(iw,int(right)+3),lower)
            if any(sum(abs(a-b) for a,b in zip(box,old[1]))<10 for old in proposals): continue
            proposals.append((support,box))
    return [tuple(int(round(value/scale)) for value in box) for _,box in sorted(proposals,reverse=True)[:24]]
