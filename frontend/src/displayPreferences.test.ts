import {afterEach,describe,expect,it,vi} from 'vitest';
import {readDisplayPreferences,saveDisplayPreferences} from './displayPreferences';

afterEach(()=>vi.unstubAllGlobals());

describe('display animation preference',()=>{
 it('keeps animation enabled for older saved settings',()=>{
  vi.stubGlobal('localStorage',{getItem:()=>JSON.stringify({text:'large',contrast:'dark',hideDecorations:true})});
  expect(readDisplayPreferences().animations).toBe(true);
 });
 it('restores the disabled setting',()=>{
  let saved='';
  vi.stubGlobal('localStorage',{getItem:()=>saved,setItem:(_:string,value:string)=>{saved=value;}});
  saveDisplayPreferences({...readDisplayPreferences(),animations:false});
  expect(readDisplayPreferences().animations).toBe(false);
 });
});
