import {Info,RefreshCw} from 'lucide-react';
import type {Analysis,Kind} from './types';
import {qualityHints} from './analysisReview';
import s from './App.module.css';

interface Props {analysis:Analysis|null;onRetake:(kind:Kind)=>void}
export default function ReviewAssistance({analysis,onRetake}:Props){
 const hints=qualityHints(analysis);
 return <>
 {hints.length>0&&<section className={s.qualityHints} aria-label="Подсказки к фотографиям">{hints.map(item=><div className={s.qualityHint} key={item.kind}><div><Info size={20}/><strong>{item.label}</strong></div><ul>{item.warnings.map(warning=><li key={warning}>{warning}</li>)}</ul><button onClick={()=>onRetake(item.kind)}><RefreshCw size={17}/> Переснять</button></div>)}</section>}

 </>;
}
