import {useEffect,useRef,useState} from 'react';
import {Info,X} from 'lucide-react';
import s from './App.module.css';

export default function Toast({message,onDismiss}:{message:string;onDismiss:()=>void}){
 const [leaving,setLeaving]=useState(false);
 const pointer=useRef<{x:number;y:number}|null>(null);
 useEffect(()=>{const timer=window.setTimeout(()=>setLeaving(true),5500);return()=>window.clearTimeout(timer);},[message]);
 useEffect(()=>{if(!leaving)return;const timer=window.setTimeout(onDismiss,240);return()=>window.clearTimeout(timer);},[leaving,onDismiss]);
 return <div className={s.toast} data-leaving={leaving} role="status" aria-live="polite" onPointerDown={event=>{if((event.target as HTMLElement).closest('button'))return;pointer.current={x:event.clientX,y:event.clientY};event.currentTarget.setPointerCapture(event.pointerId);}} onPointerUp={event=>{if(pointer.current&&Math.abs(event.clientX-pointer.current.x)>72&&Math.abs(event.clientY-pointer.current.y)<65)setLeaving(true);pointer.current=null;}} onPointerCancel={()=>{pointer.current=null;}}><Info size={21}/><span>{message}</span><button type="button" aria-label="Закрыть сообщение" onClick={()=>setLeaving(true)}><X size={18}/></button></div>;
}
