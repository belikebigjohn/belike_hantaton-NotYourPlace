import {afterEach,describe,expect,it,vi} from 'vitest';
import {getMessengerEnvironment,isMaxContainer} from './maxAdapter';

describe('MAX container layout',()=>{
 afterEach(()=>vi.unstubAllGlobals());
 it('uses the full-screen layout when the bridge exists without enabling authenticated MAX actions',()=>{
  vi.stubGlobal('window',{WebApp:{initData:''},location:{hash:''}});
  expect(isMaxContainer()).toBe(true);
  expect(getMessengerEnvironment()).toBe('browser');
 });
});
