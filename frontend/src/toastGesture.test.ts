import {describe,expect,it} from 'vitest';
import {shouldDismissToastSwipe} from './toastGesture';

describe('toast swipe',()=>{
 it('dismisses with a horizontal or upward swipe',()=>{
  expect(shouldDismissToastSwipe(-64,9)).toBe(true);
  expect(shouldDismissToastSwipe(60,-8)).toBe(true);
  expect(shouldDismissToastSwipe(8,-60)).toBe(true);
 });
 it('keeps the notice during a tap or vertical page scroll',()=>{
  expect(shouldDismissToastSwipe(12,4)).toBe(false);
  expect(shouldDismissToastSwipe(4,70)).toBe(false);
  expect(shouldDismissToastSwipe(45,42)).toBe(false);
 });
});
