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

/* ---------- constants */

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

/* ---------- prototypes/EXAMPLE.C */

/* ---------- globals */

extern struct projectile_material_response_definition default_projectile_material_response;

/* ---------- public code */

#endif // __PROJECTILE_DEFINITIONS_H
