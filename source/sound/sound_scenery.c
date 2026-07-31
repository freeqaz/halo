/*
SOUND_SCENERY.C

symbols in this file:
001BF330 0030:
	_sound_scenery_new (0000)
001BF360 0010:
	_sound_scenery_delete (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "sound_scenery.h"

#include "objects/objects.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

/* ---------- public code */

boolean sound_scenery_new(
	long object_index)
{
	struct object_datum *object= object_get_and_verify_type(object_index, _object_mask_sound_scenery);

	SET_FLAG(object->object.flags, _object_shadowless_bit, TRUE);

	return TRUE;
}

void sound_scenery_delete(
	long object_index)
{
	return;
}

/* ---------- private code */
