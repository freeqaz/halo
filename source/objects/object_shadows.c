/*
OBJECT_SHADOWS.C

symbols in this file:
0012B870 0010:
	_code_0012b870 (0000)
0012B880 0050:
	_code_0012b880 (0000)
0012B8D0 0080:
	_object_build_shadow (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "objects.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* struct layout inferred from access widths/offsets only: a copied radius, an invalid-extents
   bounding box (matches real_rectangle3d's x0/x1/y0/y1/z0/z1 min/max convention used elsewhere in
   this repo, e.g. breakable_surfaces.c), and two shorts whose purpose beyond the count>0 check at
   the end of object_build_shadow is not evidenced anywhere in this unit. */
struct object_shadow_data
{
	real radius;
	real_rectangle3d bounds;
	short count;
	short flags;
};

/* ---------- prototypes */

static void *code_0012b870(long object_index);
static void code_0012b880(
	long object_index,
	long argument2,
	struct object_shadow_data *shadow);

/* ---------- globals */

/* ---------- public code */

boolean object_build_shadow(
	long object_index,
	long argument2,
	struct object_shadow_data *shadow)
{
	struct object_datum *object= object_get(object_index);
	struct object_definition *definition= object_definition_get(object->definition_index);
	boolean result= FALSE;

	shadow->radius= definition->object.bounding_radius;
	shadow->bounds.x0= FLT_MAX;
	shadow->bounds.x1= -FLT_MAX;
	shadow->bounds.y0= FLT_MAX;
	shadow->bounds.y1= -FLT_MAX;
	shadow->bounds.z0= FLT_MAX;
	shadow->bounds.z1= -FLT_MAX;
	shadow->count= 0;
	shadow->flags= 0;

	code_0012b870(object_index);

	code_0012b880(object->object.first_child_object_index, argument2, shadow);

	if (shadow->count>0)
	{
		result= TRUE;
	}

	return result;
}

/* ---------- private code */

static void *code_0012b870(
	long object_index)
{
	return object_get(object_index);
}

static void code_0012b880(
	long object_index,
	long argument2,
	struct object_shadow_data *shadow)
{
	if (object_index!=NONE)
	{
		do
		{
			struct object_datum *object= object_get(object_index);

			code_0012b870(object_index);

			code_0012b880(object->object.first_child_object_index, argument2, shadow);

			object_index= object->object.next_object_index;
		} while (object_index!=NONE);
	}

	return;
}
