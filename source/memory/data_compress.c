/*
DATA_COMPRESS.C

symbols in this file:
00109360 0070:
	_data_compress (0000)
001093D0 0040:
	_data_decompressed_size (0000)
00109410 0060:
	_data_decompress (0000)
*/

/* ---------- headers */

#include "cseries.h"

#include "byte_swapping.h"
#include "zlib.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

/* ---------- globals */

/* ---------- public code */

boolean data_compress(
	void *source,
	unsigned long source_size,
	void *destination,
	unsigned long *destination_size,
	unsigned long destination_size_max)
{
	boolean success= FALSE;

	if (destination_size_max>=4)
	{
		*((unsigned long *)destination)= SWAP4(source_size);
		*destination_size= destination_size_max-4;

		if (compress2((Bytef *)destination+4, destination_size, (Bytef *)source, source_size, 9)==0)
		{
			*destination_size += 4;
			success= TRUE;
		}
	}

	return success;
}

long data_decompressed_size(
	void *source,
	unsigned long source_size)
{
	long result= 0;

	if (source_size>=4)
	{
		result= SWAP4(*((unsigned long *)source));
	}

	return result;
}

boolean data_decompress(
	void *source,
	unsigned long source_size,
	void *destination,
	unsigned long *destination_size,
	unsigned long destination_size_max)
{
	boolean success= FALSE;
	unsigned long decompressed_size= 0;

	if (source_size>=4)
	{
		decompressed_size= SWAP4(*((unsigned long *)source));
	}
	*destination_size= decompressed_size;

	if (uncompress((Bytef *)destination, destination_size, (Bytef *)source+4, source_size)==0)
	{
		success= TRUE;
	}

	return success;
}

/* ---------- private code */
