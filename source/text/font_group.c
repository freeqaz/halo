/*
FONT_GROUP.C

symbols in this file:
0018C840 0070:
	_font_get_character_by_ascii_code (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "font_group.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

/* ---------- public code */

struct font_character *font_get_character_by_ascii_code(
	struct font_header *header,
	unsigned short character)
{
	struct tag_block *character_table= TAG_BLOCK_GET_ELEMENT(&header->character_tables, character>>8, struct tag_block);
	struct font_character *result= NULL;

	if (character_table->count>0)
	{
		short *character_index_address= (character_table->count==0x100) ?
			TAG_BLOCK_GET_ELEMENT(character_table, character&0xFF, short) :
			NULL;
		short character_index= *character_index_address;

		if (character_index!=NONE)
		{
			result= TAG_BLOCK_GET_ELEMENT(&header->characters, character_index, struct font_character);
		}
	}

	return result;
}

/* ---------- private code */
