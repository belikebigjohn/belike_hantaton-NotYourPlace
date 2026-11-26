import {useEffect,useRef} from 'react';
import {X} from 'lucide-react';
import type {DisplayPreferences} from './displayPreferences';
import {defaultDisplay} from './displayPreferences';
import s from './App.module.css';
interface Props {open:boolean;value:DisplayPreferences;onChange:(value:DisplayPreferences)=>void;onClose:()=>void}
export default function DisplaySettings({open,value,onChange,onClose}:Props){
 const heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{if(open)heading.current?.focus();},[open]);
 return <section id="display-settings" className={s.displaySettings} data-open={open} aria-hidden={!open} inert={!open} aria-labelledby="display-title" onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();onClose();}}}>
 <div><h2 id="display-title" tabIndex={-1} ref={heading}>Настройки отображения</h2><button className={s.iconButton} onClick={onClose} aria-label="Закрыть настройки отображения"><X/></button></div>
 <fieldset><legend>Размер текста</legend>{([['normal','Обычный'],['large','Крупный'],['extra','Очень крупный']] as const).map(([id,label])=><label key={id}><input type="radio" name="display-text" value={id} checked={value.text===id} onChange={()=>onChange({...value,text:id})}/>{label}</label>)}</fieldset>
 <fieldset><legend>Цветовая схема</legend>{([['normal','Стандартная'],['light','Чёрный текст на белом'],['dark','Белый текст на чёрном']] as const).map(([id,label])=><label key={id}><input type="radio" name="display-contrast" value={id} checked={value.contrast===id} onChange={()=>onChange({...value,contrast:id})}/>{label}</label>)}</fieldset>
 <label className={s.displayOption}><input type="checkbox" checked={value.hideDecorations} onChange={event=>onChange({...value,hideDecorations:event.target.checked})}/>Скрыть декоративные изображения</label>
 <label className={s.displayOption}><input type="checkbox" checked={value.animations} onChange={event=>onChange({...value,animations:event.target.checked})}/>Включить анимацию</label>
 <button className={s.secondary} onClick={()=>onChange({...defaultDisplay})}>Вернуть обычный вид</button>
 </section>;
}
