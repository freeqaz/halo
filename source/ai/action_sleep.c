/*
ACTION_SLEEP.C

symbols in this file:
00008660 0030:
	_action_sleep_control (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "actions.h"

#include "actors.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

void action_sleep_control(long actor_index);

/* ---------- globals */

/* ---------- public code */

void action_sleep_control(
	long actor_index)
{
	struct actor_datum *actor = actor_get(actor_index);

	actor->orders.look.idle_look_type = 0;
}

/* ---------- private code */
