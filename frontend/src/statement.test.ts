import {describe,it,expect} from 'vitest';
import {statementForDraft} from './statement';
import type {Draft} from './types';
const data={plate:'P999PP99',address:'Тестовый адрес',observed_at:'2026-11-22T10:00:00+05:00',designation:'Обозначение требует проверки',observation:'',analysis:null} as Draft;
describe('observations and demo registry in generated statement',()=>{
 it('reports absence only in the named demonstration database',()=>{const text=statementForDraft(data);expect(text).toContain('не найден');expect(text).toContain('демонстрационной базе');expect(text).toContain('Проверка по государственным реестрам не проводилась');expect(text).not.toContain('знак «Инвалид» мне не был виден');});
 it('does not falsely report absence for a matched fixture or incomplete plate',()=>{expect(statementForDraft({...data,plate:'A123BC77'})).toContain('номером найден в демонстрационной базе');expect(statementForDraft({...data,plate:'99'})).not.toContain('автоматической проверки системы');});
 it('includes sign observation only when explicitly chosen by a person',()=>{const analysis={plate_review:{scene_value:data.plate,plate_value:data.plate,confirmed:true,disability_sign_not_visible:true}} as NonNullable<Draft['analysis']>;const text=statementForDraft({...data,analysis});expect(text).toContain('При осмотре автомобиля опознавательный знак «Инвалид» мне не был виден');expect(text).toContain('Прошу проверить наличие знака');expect(text).not.toContain('нарушитель');expect(statementForDraft({...data,analysis:{...analysis,plate_review:{...analysis.plate_review!,disability_sign_not_visible:false}}})).not.toContain('мне не был виден');});
});
