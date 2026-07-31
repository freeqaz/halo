/*
OBJECT_DELETED_PROCS.C

symbols in this file:
00128700 0030:
	_object_deleted_procs_call (0000)
0030B378 000c:
	_object_deleted_procs (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "objects.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

extern void ai_handle_deleted_object(long deleted_object_index);
extern void players_handle_deleted_object(long deleted_object_index);

/* ---------- globals */

object_deleted_proc object_deleted_procs[]=
{
	objects_fix_for_deleted_object,
	ai_handle_deleted_object,
	players_handle_deleted_object,
};

/* ---------- public code */

void object_deleted_procs_call(
	long deleted_object_index)
{
	object_deleted_proc const *proc= object_deleted_procs;
	long count= NUMBEROF(object_deleted_procs);

	do
	{
		(*proc)(deleted_object_index);
		proc++;
	}
	while (--count);

	return;
}

/* ---------- private code */
