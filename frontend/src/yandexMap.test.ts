import {describe,it,expect} from 'vitest';
import {validMapPoint,widgetUrl} from './yandexMap';
describe('Yandex map coordinate boundary',()=>{
 it('accepts zero coordinates and rejects empty, nonnumeric or out of range values',()=>{expect(validMapPoint(0,0)).toEqual([0,0]);for(const pair of [[null,60],[' ',60],[91,60],[56,181],['NaN',60],[true,60]])expect(validMapPoint(...pair as [unknown,unknown])).toBeNull();});
 it('passes longitude first to Yandex and only places a marker when a point is known',()=>{const url=new URL(widgetUrl([56.8,60.6]));expect(url.searchParams.get('ll')).toBe('60.6,56.8');expect(url.searchParams.get('pt')).toBe('60.6,56.8,pm2rdm');expect(new URL(widgetUrl(null)).searchParams.has('pt')).toBe(false);});
});
