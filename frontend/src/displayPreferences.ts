export interface DisplayPreferences {text:'normal'|'large'|'extra';contrast:'normal'|'light'|'dark';hideDecorations:boolean}
export const defaultDisplay:DisplayPreferences={text:'normal',contrast:'normal',hideDecorations:false};
export function readDisplayPreferences():DisplayPreferences{
 try{const saved=JSON.parse(localStorage.getItem('chuzhoe-display')||'null');return {text:['normal','large','extra'].includes(saved?.text)?saved.text:'normal',contrast:['normal','light','dark'].includes(saved?.contrast)?saved.contrast:'normal',hideDecorations:saved?.hideDecorations===true};}catch{return {...defaultDisplay};}
}
export function saveDisplayPreferences(value:DisplayPreferences){try{localStorage.setItem('chuzhoe-display',JSON.stringify(value));}catch{/* Current selection remains usable when storage is unavailable. */}}
