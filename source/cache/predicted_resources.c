/*
PREDICTED_RESOURCES.C

symbols in this file:
001AD870 0090:
	_code_001ad870 (0000)
001AD900 0080:
	_predicted_resources_precache (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "predicted_resources.h"

#include "bitmaps/bitmap_group.h"
#include "cache/sound_cache.h"
#include "cache/texture_cache.h"
#include "sound/sound_definitions.h"
#include "tag_files/tag_groups.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

/* ---------- public code */

static void code_001ad870(
	long tag_index)
{
	struct sound_definition *sound_definition= tag_get(SOUND_DEFINITION_TAG, tag_index);
	short pitch_range_index;

	for (pitch_range_index= 0; pitch_range_index<sound_definition->pitch_ranges.count; pitch_range_index++)
	{
		struct sound_pitch_range *pitch_range= TAG_BLOCK_GET_ELEMENT(&sound_definition->pitch_ranges, pitch_range_index, struct sound_pitch_range);
		short permutation_index;

		for (permutation_index= 0; permutation_index<pitch_range->actual_permutation_count; permutation_index++)
		{
			_sound_cache_sound_request(TAG_BLOCK_GET_ELEMENT(&pitch_range->permutations, permutation_index, struct sound_permutation), FALSE, TRUE, FALSE);
		}
	}

	return;
}

void predicted_resources_precache(
	struct tag_block *predicted_resources)
{
	short resource_index;

	for (resource_index= 0; resource_index<predicted_resources->count; resource_index++)
	{
		struct predicted_resource *resource= TAG_BLOCK_GET_ELEMENT(predicted_resources, resource_index, struct predicted_resource);

		switch (resource->type)
		{
		case _predicted_resource_bitmap:
			_texture_cache_bitmap_get_hardware_format(
				TAG_BLOCK_GET_ELEMENT(&((struct bitmap_group *)tag_get(BITMAP_GROUP_TAG, resource->tag_index))->bitmaps, resource->resource_index, struct bitmap_data),
				FALSE,
				TRUE);
			break;

		case _predicted_resource_sound:
			code_001ad870(resource->tag_index);
			break;
		}
	}

	return;
}

/* ---------- private code */
