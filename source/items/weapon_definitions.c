/*
WEAPON_DEFINITIONS.C

symbols in this file:
000EA410 00c0:
	_weapon_definition_get_damage_potential (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "weapon_definitions.h"

#include "items/projectile_definitions.h"
#include "game/game_globals.h"
#include "objects/damage_effect_definitions.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

/* ---------- public code */

real weapon_definition_get_damage_potential(long weapon_index, real *rate_of_fire)
{
	struct weapon_definition *weapon= weapon_definition_get(weapon_index);
	struct weapon_trigger_definition *trigger= TAG_BLOCK_GET_ELEMENT(&weapon->weapon.triggers, 0, struct weapon_trigger_definition);
	real damage_potential= 0.0f;

	if (rate_of_fire)
	{
		*rate_of_fire= trigger->final_rate_of_fire;
	}

	if (trigger->projectile.index!=NONE)
	{
		struct projectile_definition *projectile_definition= projectile_definition_get(trigger->projectile.index);

		if (projectile_definition->projectile.impact_damage.index!=NONE)
		{
			struct damage_effect_definition *damage_effect_definition= damage_effect_definition_get(projectile_definition->projectile.impact_damage.index);
			damage_potential= (damage_effect_definition->damage.damage_upper_bound + damage_effect_definition->damage.damage_lower_bound)*0.5f;
		}

		if (projectile_definition->projectile.detonation_damage.index!=NONE)
		{
			struct damage_effect_definition *damage_effect_definition= damage_effect_definition_get(projectile_definition->projectile.detonation_damage.index);
			damage_potential+= (damage_effect_definition->damage.damage_upper_bound + damage_effect_definition->damage.damage_lower_bound)*0.5f;
		}
	}

	return damage_potential;
}

/* ---------- private code */
