/*
GAME_ENGINE_LIST.C

symbols in this file:
002DE510 0020:
	_game_engines (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "game_engine.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

extern struct game_engine ctf_engine;
extern struct game_engine slayer_engine;
extern struct game_engine oddball_engine;
extern struct game_engine king_engine;
extern struct game_engine race_engine;
extern struct game_engine stub_engine;

/* ---------- globals */

struct game_engine *game_engines[8]=
{
	NULL,
	&ctf_engine,
	&slayer_engine,
	&oddball_engine,
	&king_engine,
	&race_engine,
	&stub_engine,
	NULL
};

/* ---------- public code */

/* ---------- private code */
