import {useId,useState} from 'react';
import type {ReactNode} from 'react';
import {ChevronRight} from 'lucide-react';
import s from './App.module.css';

interface Props {title:string;children:ReactNode;defaultOpen?:boolean;className?:string}
export default function Disclosure({title,children,defaultOpen=false,className=''}:Props){
 const [open,setOpen]=useState(defaultOpen);
 const id=useId();
 return <section className={`${s.disclosure} ${className}`} data-open={open}>
  <h2 className={s.disclosureHeading}><button type="button" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(value=>!value)}>{title}<ChevronRight size={19} aria-hidden="true"/></button></h2>
  <div id={id} className={s.disclosureBody} aria-hidden={!open} inert={!open}><div className={s.disclosureInner}>{children}</div></div>
 </section>;
}
