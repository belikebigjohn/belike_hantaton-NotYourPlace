import {useId,useEffect,useRef,useState} from 'react';
import {latinPlateValue,plateParts} from './plateFormat';
import s from './App.module.css';

interface Props {label:string;value:string;onChange:(value:string)=>void}
export default function RussianPlateInput({label,value,onChange}:Props){
 const id=useId(),lastEmitted=useRef(value),[parts,setParts]=useState(()=>plateParts(value));
 useEffect(()=>{if(value!==lastEmitted.current){setParts(plateParts(value));lastEmitted.current=value;}},[value]);
 const slots=[{key:'letter',max:1,pattern:/[ABCEHKMOPTXY]/g,hint:'Первая буква'},{key:'digits',max:3,pattern:/[0-9]/g,hint:'Три цифры'},{key:'suffix',max:2,pattern:/[ABCEHKMOPTXY]/g,hint:'Две буквы'},{key:'region',max:3,pattern:/[0-9]/g,hint:'Регион'}] as const;
 return <fieldset className={s.registrationField}><legend>{label}</legend><div className={s.registrationPlate}>
 {slots.map((slot,index)=><div key={slot.key} className={index===3?s.registrationRegion:s.registrationSlot}>
 <input id={`${id}-${slot.key}`} aria-label={`${label}: ${slot.hint.toLowerCase()}`} value={parts[slot.key]} maxLength={slot.max} inputMode={index===1||index===3?'numeric':'text'} autoCapitalize="characters" autoComplete="off" spellCheck={false} placeholder={['A','123','BC','77'][index]}
 onPaste={event=>{const pasted=latinPlateValue(event.clipboardData.getData('text'));if(/^[ABCEHKMOPTXY]\d{3}[ABCEHKMOPTXY]{2}\d{2,3}$/.test(pasted)){event.preventDefault();onChange(pasted);}}}
 onChange={event=>{const next={...parts,[slot.key]:(latinPlateValue(event.target.value).match(slot.pattern)||[]).join('').slice(0,slot.max)};setParts(next);lastEmitted.current=next.letter+next.digits+next.suffix+next.region;onChange(lastEmitted.current);if(next[slot.key].length===slot.max&&index<3)document.getElementById(`${id}-${slots[index+1].key}`)?.focus();}}/>
 {index===3&&<span className={s.registrationCountry} aria-hidden="true">RUS <i/></span>}
 </div>)}
 </div></fieldset>;
}
