/* FUN_0047c060  —  game@0x0047c060  [unknown]  status=unknown
 * Harvested Ghidra decompilation (workspace halo, /cachebeta.exe-d7dc40). Callees show
 * applied names where known. Ghidra label: FUN_0047c060-0047c060.
 * Note: seeded from Ghidra analysis of cachebeta.exe (refcount 5536)
 */

void FUN_0047c060(char *param_1,undefined4 param_2,undefined4 param_3,char param_4)

{
  undefined *puVar1;
  
  if (param_4 != '\0') {
    FUN_004813d0(0);
  }
  if (param_1 == (char *)0x0) {
    param_1 = "<no reason given>";
  }
  puVar1 = &DAT_006573e4;
  if (param_4 == '\0') {
    puVar1 = &DAT_006573dc;
  }
  FUN_0047da00(2,"EXCEPTION %s in %s,#%d: %s",puVar1,param_2,param_3,param_1);
  return;
}
