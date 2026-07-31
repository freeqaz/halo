/*
SOUND_CACHE.H

header included in hcex build.
*/

#ifndef __SOUND_CACHE_H
#define __SOUND_CACHE_H
#pragma once

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

struct sound_permutation;

/* ---------- prototypes/XBOX_SOUND_CACHE.C */

unsigned char _sound_cache_sound_request(struct sound_permutation *sound, unsigned char block, unsigned char load, unsigned char reference);

/* ---------- globals */

/* ---------- public code */

#endif // __SOUND_CACHE_H
