/*
GARBAGE.C

symbols in this file:
000E6010 0040:
	_garbage_update (0000)
000E6050 0050:
	_garbage_new (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "garbage.h"

#include "objects/objects.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

/* ---------- public code */

boolean garbage_update(
	long garbage_index)
{
	struct garbage_datum *garbage= garbage_get(garbage_index);
	boolean active= (--garbage->garbage.destroy_timer>0);

	if (!active)
	{
		object_delete(garbage_index);
	}

	return active;
}

boolean garbage_new(
	long garbage_index)
{
	struct garbage_datum *garbage= garbage_get(garbage_index);

	object_set_garbage(garbage_index, TRUE);
	SET_FLAG(garbage->object.flags, _object_shadowless_bit, TRUE);
	SET_FLAG(garbage->object.flags, _object_deleted_when_deactivated_bit, TRUE);
	garbage->garbage.destroy_timer= seed_random_range(get_global_random_seed_address(), GARBAGE_TIMER_MIN, GARBAGE_TIMER_MAX);

	return TRUE;
}

/* ---------- private code */
