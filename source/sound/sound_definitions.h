/*
SOUND_DEFINITIONS.H

file has inline function assertions.
*/

#ifndef __SOUND_DEFINITIONS_H
#define __SOUND_DEFINITIONS_H
#pragma once

/* ---------- headers */

#include "math/real_math.h"
#include "tag_files/tag_groups.h"

/* ---------- constants */

enum
{
	SOUND_DEFINITION_TAG = 'snd!',
	SOUND_DEFINITION_VERSION = 4,
	MAXIMUM_PROMOTION_RULES_PER_SOUND = 4,
	MAXIMUM_PITCH_RANGES_PER_SOUND = 8,
	MAXIMUM_PERMUTATIONS_PER_PITCH_RANGE = 256,
	MAXIMUM_PERMUTATIONS_PER_RANDOM_PITCH_RANGE = 32,
	MAXIMUM_SOUND_DATA_SIZE = 0x400000,
	MAXIMUM_SOUND_MOUTH_DATA_SIZE = 8192,
	SOUND_MOUTH_SAMPLES_PER_SECOND = 30,
	MAXIMUM_SOUND_SUBTITLE_DATA_SIZE = 512,
	SOUND_COMPRESSION_BLOCK_SIZE = 64,
};

enum
{
	LOOPING_SOUND_DEFINITION_TAG = 'lsnd',
	LOOPING_SOUND_DEFINITION_VERSION = 3,
	CUSTOM_MUSIC_PLAY_ID = 'mply',
	MAXIMUM_TRACKS_PER_LOOPING_SOUND = 4,
	MAXIMUM_DETAIL_SOUNDS_PER_LOOPING_SOUND = 32,
};

/* ---------- macros */

/* ---------- structures */

struct sound_permutation
{
	char name[32];
	real skip_fraction;
	real gain;
	short duplicate_compression;
	short next_permutation_index;
	long cache_block_index;
	void *cache_base_address;
	long cache_tag_index;
	long unused0;
	long runtime_tag_index;
	struct tag_data samples;
	struct tag_data mouth_data;
	struct tag_data subtitle_data;
};

struct sound_pitch_range
{
	char name[32];
	real natural_pitch;
	real bend_lower_bound;
	real bend_upper_bound;
	short actual_permutation_count;
	unsigned short plenty_of_unused_space_here;
	real runtime_oo_natural_pitch;
	unsigned long runtime_permutation_flags;
	short runtime_last_permutation_index;
	short runtime_discarded_permutation_index;
	struct tag_block permutations;
};

struct sound_scale_modifiers
{
	real skip_fraction;
	real gain;
	real pitch;
	long unused0[3];
};

struct sound_definition
{
	long flags;
	short class_index;
	short sample_rate;
	real minimum_distance;
	real maximum_distance;
	real skip_fraction;
	real pitch_lower_bound;
	real pitch_upper_bound;
	real inner_cone_angle;
	real outer_cone_angle;
	real outer_cone_gain;
	real gain;
	real maximum_bend;
	long unused[3];
	struct sound_scale_modifiers scale_lower_bound;
	struct sound_scale_modifiers scale_upper_bound;
	short encoding;
	short compression;
	struct tag_reference promotion_sound;
	short promotion_count;
	unsigned short pad2;
	long runtime_maximum_play_time;
	long runtime_promotion_counter;
	long runtime_promotion_time;
	long runtime_scripting_time;
	long runtime_scripting_sound_index;
	struct tag_block pitch_ranges;
};

/* ---------- prototypes/EXAMPLE.C */

/* ---------- globals */

/* ---------- public code */

#endif // __SOUND_DEFINITIONS_H
