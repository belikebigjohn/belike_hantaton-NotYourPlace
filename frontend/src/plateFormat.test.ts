import {describe,it,expect} from 'vitest';
import {isRussianPlate,latinPlateValue,plateParts} from './plateFormat';
import {lookupDemoVehicle} from './registryFixtures';
describe('Russian plate fields and demo lookup',()=>{
 it('accepts full numbers with two or three region digits',()=>{expect(isRussianPlate('A123BC77')).toBe(true);expect(isRussianPlate('А123ВС199')).toBe(true);expect(plateParts('А123ВС199')).toEqual({letter:'A',digits:'123',suffix:'BC',region:'199'});});
 it('rejects fragments, incomplete regions and forbidden letters',()=>{for(const value of ['77','123','A123BC7','A123BC7777','D123BC77','A123BC77Z'])expect(isRussianPlate(value)).toBe(false);});
 it('normalizes keyboard lookalikes to Latin without inventing characters',()=>{expect(latinPlateValue('а123вс 77')).toBe('A123BC77');});
 it('finds fixtures only by whole normalized numbers; absence never changes eligibility',()=>{expect(lookupDemoVehicle('А123ВС77')?.name).toBe('Алексей Примеров');expect(lookupDemoVehicle('A001AA86')).toBeUndefined();expect(lookupDemoVehicle('77')).toBeUndefined();});
});
