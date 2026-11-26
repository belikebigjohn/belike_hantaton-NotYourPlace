import {useEffect,useRef,useState} from 'react';
import {Info,X} from 'lucide-react';
import s from './App.module.css';
import {shouldDismissToastSwipe} from './toastGesture';

export default function Toast({message,onDismiss}:{message:string;onDismiss:()=>void}){
 const [leaving,setLeaving]=useState(false);
 const swipe=useRef<{x:number;y:number}|null>(null);
 useEffect(()=>{const timer=window.setTimeout(()=>setLeaving(true),5500);return()=>window.clearTimeout(timer);},[message]);
 useEffect(()=>{if(!leaving)return;const timer=window.setTimeout(onDismiss,240);return()=>window.clearTimeout(timer);},[leaving,onDismiss]);
 const finish=(x:number,y:number)=>{if(swipe.current&&shouldDismissToastSwipe(x-swipe.current.x,y-swipe.current.y))setLeaving(true);swipe.current=null;};
 return <div className={s.toast} data-leaving={leaving} role="status" aria-live="polite"
  onTouchStart={event=>{if(!(event.target as HTMLElement).closest('button')){const touch=event.touches[0];swipe.current={x:touch.clientX,y:touch.clientY};}}}
  onTouchEnd={event=>{const touch=event.changedTouches[0];if(touch)finish(touch.clientX,touch.clientY);}}
  onTouchCancel={()=>{swipe.current=null;}}
  onPointerDown={event=>{if(event.pointerType==='touch'||(event.target as HTMLElement).closest('button'))return;swipe.current={x:event.clientX,y:event.clientY};event.currentTarget.setPointerCapture(event.pointerId);}}
  onPointerUp={event=>{if(event.pointerType!=='touch')finish(event.clientX,event.clientY);}}
  onPointerCancel={()=>{swipe.current=null;}}><Info size={21}/><span>{message}</span><button type="button" aria-label="Закрыть сообщение" onClick={()=>setLeaving(true)}><X size={18}/></button></div>;
}
