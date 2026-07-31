/*
PROJECTILE_DEFINITIONS.H

header included in hcex build.
*/

#ifndef __PROJECTILE_DEFINITIONS_H
#define __PROJECTILE_DEFINITIONS_H
#pragma once

/* ---------- headers */

#include "math/real_math.h"
#include "tag_files/tag_groups.h"
#include "objects/object_definitions.h"

/* ---------- constants */

enum
{
	PROJECTILE_DEFINITION_TAG = 'proj',
	PROJECTILE_DEFINITION_VERSION = 5,
};

enum
{
	_projectile_response_disappear = 0,
	_projectile_response_detonate,
	_projectile_response_reflect,
	_projectile_response_penetrate,
	_projectile_response_attach,
	NUMBER_OF_PROJECTILE_MATERIAL_RESPONSES,
};

enum
{
	_projectile_material_response_scale_effects_by_damage = 0,
	_projectile_material_response_scale_effects_by_angle,
	NUMBER_OF_PROJECTILE_MATERIAL_RESPONSE_SCALE_MODES,
};

/* ---------- macros */

#define projectile_definition_get(index) ((struct projectile_definition *)tag_get(PROJECTILE_DEFINITION_TAG, index))

/* ---------- structures */

struct projectile_material_response_definition
{
	word flags;
	short default_response;
	struct tag_reference default_effect;
	long unused0[4];

	short possible_response;
	word possible_response_flags;
	real possible_response_skip_fraction;
	real possible_response_minimum_angle;
	real possible_response_maximum_angle;
	real possible_response_minimum_velocity;
	real possible_response_maximum_velocity;
	struct tag_reference possible_response_effect;
	long unused1[4];

	short scale_effects_by;
	word pad;
	real angle_noise;
	real velocity_noise;
	struct tag_reference detonation_effect;
	long unused2[6];

	real penetration_initial_friction;
	real penetration_maximum_distance;
	real reflection_parallel_friction;
	real reflection_perpendicular_friction;
};

struct _projectile_definition
{
	unsigned long flags;
	short detonation_timer_mode;
	short impact_noise;
	short function_modes[4];
	struct tag_reference super_detonation_effect;
	real danger_perception_radius;
	real collision_radius;
	real arming_time;
	real danger_radius;
	struct tag_reference detonation_effect;
	real detonation_minimum_time;
	real detonation_maximum_time;
	real detonation_minimum_velocity;
	real detonation_maximum_range;
	real air_gravity_scale;
	real air_minimum_damage_distance;
	real air_maximum_damage_distance;
	real water_gravity_scale;
	real water_minimum_damage_distance;
	real water_maximum_damage_distance;
	real initial_velocity;
	real final_velocity;
	real guided_angular_velocity;
	short detonation_noise;
	word unused1;
	struct tag_reference detonation_timer_started;
	struct tag_reference flyby_sound;
	struct tag_reference detonation_damage;
	struct tag_reference impact_damage;
	long unused2[3];
	struct tag_block material_responses;			// projectile_material_response_definition
};

struct projectile_definition
{
	struct _object_definition object;
	struct _projectile_definition projectile;
};

/* ---------- prototypes/EXAMPLE.C */

/* ---------- globals */

extern struct projectile_material_response_definition default_projectile_material_response;

/* ---------- public code */

#endif // __PROJECTILE_DEFINITIONS_H
