interface MaxHost extends Window {WebApp?:{initData?:string;ready?:()=>void;expand?:()=>void}}
export function getMaxInitData():string {
  if(typeof window==='undefined')return '';
  const host=window as MaxHost;
  const fromBridge=host.WebApp?.initData;
  if(fromBridge)return fromBridge;
  const fragment=new URLSearchParams(window.location.hash.slice(1));
  return fragment.get('WebAppData')||'';
}
export function getMessengerEnvironment(): 'max' | 'browser' {return getMaxInitData()?'max':'browser';}
export function isMaxContainer():boolean {return typeof window!=='undefined'&&Boolean((window as MaxHost).WebApp||getMaxInitData());}
export function readyMax():void {if(typeof window==='undefined')return;const host=window as MaxHost;host.WebApp?.ready?.();host.WebApp?.expand?.();}
