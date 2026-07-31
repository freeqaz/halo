/*
NETWORK_GAME_UI.C

symbols in this file:
0011AE30 0060:
	_network_game_get_random_player_name (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "network_game_ui.h"

#include "real_math.h"
#include "tag_groups.h"
#include "text_group.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

/* ---------- public code */

unsigned short *network_game_get_random_player_name(void)
{
	unsigned short *result = (unsigned short *)L"";
	long tag_index = tag_loaded(UNICODE_STRING_LISTS_GROUP_TAG, "ui\\random_player_names");

	if (tag_index != NONE)
	{
		struct tag_block *strings = (struct tag_block *)tag_get(UNICODE_STRING_LISTS_GROUP_TAG, tag_index);

		if (strings)
		{
			short count = strings->count - 1;

			result = unicode_string_list_get_string(tag_index, seed_random_range(get_global_local_random_seed_address(), 0, count));
		}
	}

	return result;
}

/* ---------- private code */
