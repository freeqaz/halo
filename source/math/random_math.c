/*
RANDOM_MATH.C

symbols in this file:
000FA8B0 0010:
	_lock_global_random_seed (0000)
000FA8C0 0030:
	_unlock_global_random_seed (0000)
000FA8F0 0040:
	_get_global_random_seed_address (0000)
000FA930 0010:
	_get_random_seed (0000)
000FA940 0010:
	_get_global_local_random_seed_address (0000)
000FA950 0010:
	_random_seed_debug_log (0000)
000FA960 0020:
	_get_number_suitable_for_initializing_random_seed (0000)
000FA980 00c0:
	_random_math_initialize (0000)
000FAA40 0020:
	_random_math_dispose (0000)
000FAA60 0030:
	_real_seed_random (0000)
000FAA90 0040:
	_real_seed_random_range (0000)
000FAAD0 0020:
	_seed_random (0000)
000FAAF0 0030:
	_seed_random_range (0000)
000FAB20 0080:
	_code_000fab20 (0000)
000FABA0 0040:
	_seed_random_direction3d (0000)
000FABE0 0100:
	_seed_random_orientation (0000)
000FACE0 0100:
	_seed_random_vector_in_cone3d (0000)
0027AE88 0031:
	??_C@_0DB@GOKAHAFJ@unmatched?5call?5to?5unlock_random_@ (0000)
0027AEBC 0022:
	??_C@_0CC@CGOEMOHM@c?3?2halo?2SOURCE?2math?2random_math?4@ (0000)
0027AEE0 0044:
	??_C@_0EE@KKMKHIJL@you?5should?5not?5be?5using?5global?5r@ (0000)
0027AF24 001b:
	??_C@_0BL@CJPMPDBB@random_direction_geosphere?$AA@ (0000)
0027AF40 0042:
	??_C@_0EC@LPLKDAPN@index?$DO?$DN0?5?$CG?$CG?5index?$DMrandom_math_gl@ (0000)
0027AF84 002b:
	??_C@_0CL@KJMLMACI@random_math_globals?4random_direc@ (0000)
00456208 0014:
	_bss_00456208 (0000)
*/

/* ---------- headers */

#include "cseries.h"
#include "real_math.h"

#include "game/game_engine.h"
#include "geometry.h"

/* ---------- constants */

/* ---------- macros */

/* ---------- structures */

/* ---------- prototypes */

extern unsigned long system_seconds(void);

/* ---------- globals */

static struct
{
	real_vector3d *random_direction_table;
	short random_direction_table_size;
	long random_seed_lock_count;
	unsigned long global_random_seed;
	unsigned long global_local_random_seed;
} random_math_globals;

/* ---------- public code */

void lock_global_random_seed(
	void)
{
	random_math_globals.random_seed_lock_count++;
}

void unlock_global_random_seed(
	void)
{
	match_vassert(
		"c:\\halo\\SOURCE\\math\\random_math.c",
		41,
		random_math_globals.random_seed_lock_count>0,
		"unmatched call to unlock_random_seed() somewhere");

	random_math_globals.random_seed_lock_count--;
}

unsigned long *get_global_random_seed_address(
	void)
{
	match_vassert(
		"c:\\halo\\SOURCE\\math\\random_math.c",
		56,
		!game_engine_running() || random_math_globals.random_seed_lock_count==0,
		"you should not be using global random(); use local random() instead");

	return &random_math_globals.global_random_seed;
}

unsigned long get_random_seed(
	void)
{
	return random_math_globals.global_random_seed;
}

unsigned long *get_global_local_random_seed_address(
	void)
{
	return &random_math_globals.global_local_random_seed;
}

void random_seed_debug_log(
	boolean enable)
{
}

unsigned long get_number_suitable_for_initializing_random_seed(
	void)
{
	return system_seconds()^system_milliseconds()^rand();
}

void random_math_initialize(
	void)
{
	struct geosphere *random_direction_geosphere;
	short i;

	random_math_globals.global_local_random_seed = get_number_suitable_for_initializing_random_seed();

	random_direction_geosphere = geosphere_new(16);
	match_assert("c:\\halo\\SOURCE\\math\\random_math.c", 174, random_direction_geosphere);

	random_math_globals.random_direction_table = match_malloc(
		"c:\\halo\\SOURCE\\math\\random_math.c",
		176,
		random_direction_geosphere->vertex_count*sizeof(real_vector3d));

	random_math_globals.random_direction_table_size = random_direction_geosphere->vertex_count;

	for (i= 0; i<random_direction_geosphere->vertex_count; i++)
	{
		random_math_globals.random_direction_table[i] = *(real_vector3d const *)&random_direction_geosphere->vertices[i];
	}

	geosphere_dispose(random_direction_geosphere);
}

void random_math_dispose(
	void)
{
	match_free(
		"c:\\halo\\SOURCE\\math\\random_math.c",
		200,
		random_math_globals.random_direction_table);
}

real real_seed_random(
	unsigned long *seed)
{
	*seed= *seed*0x19660d+0x3c6ef35f;

	return (real)(*seed>>16)*(1.0f/65535.0f);
}

real real_seed_random_range(
	unsigned long *seed,
	real lower_bound,
	real upper_bound)
{
	real value= real_seed_random(seed);

	return value*(upper_bound-lower_bound)+lower_bound;
}

unsigned short seed_random(
	unsigned long *seed)
{
	*seed= *seed*0x19660d+0x3c6ef35f;

	return (unsigned short)(*seed>>16);
}

short seed_random_range(
	unsigned long *seed,
	short lower_bound,
	short upper_bound)
{
	unsigned long value= seed_random(seed)*(upper_bound-lower_bound);

	return lower_bound+(short)(value>>16);
}

static real_vector3d *code_000fab20(
	short index,
	real_vector3d *result)
{
	real_vector3d *entry= &random_math_globals.random_direction_table[index];

	match_assert("c:\\halo\\SOURCE\\math\\random_math.c", 250, random_math_globals.random_direction_table);
	match_assert("c:\\halo\\SOURCE\\math\\random_math.c", 251, index>=0 && index<random_math_globals.random_direction_table_size);

	*result= *entry;

	return result;
}

real_vector3d *seed_random_direction3d(
	unsigned long *seed,
	real_vector3d *direction)
{
	short table_size= random_math_globals.random_direction_table_size;

	return code_000fab20((short)(((unsigned long)(seed_random(seed)*table_size))>>16), direction);
}

void seed_random_orientation(
	unsigned long *seed,
	real_vector3d *forward,
	real_vector3d *up)
{
	real angle1;
	real phi;
	real theta;
	real cos_angle1, sin_angle1;
	real cos_phi, sin_phi;

	angle1= real_seed_random(seed);
	angle1= angle1*(_pi*2.f);

	phi= real_seed_random(seed);
	phi= phi*_pi-(_pi/2.f);

	theta= real_seed_random(seed);
	theta= theta*(_pi*2.f);

	cos_angle1= cosine(angle1);
	sin_angle1= sine(angle1);
	cos_phi= cosine(phi);
	sin_phi= sine(phi);

	forward->i= cos_phi*cos_angle1;
	forward->j= cos_phi*sin_angle1;
	forward->k= sin_phi;

	up->i= -(cos_angle1*sin_phi);
	up->j= -(sin_phi*sin_angle1);
	up->k= cos_phi;

	yaw_vectors(up, forward, sine(theta), cosine(theta));
}

real_vector3d *seed_random_vector_in_cone3d(
	unsigned long *seed,
	real_vector3d const *axis,
	real inner_cone_angle,
	real outer_cone_angle,
	real_vector3d *result)
{
	real_vector3d random_vector;
	real_vector3d perpendicular;
	short index;

	*result= *axis;

	{
		short table_size= random_math_globals.random_direction_table_size;
		unsigned long value= seed_random(seed)*table_size;

		index= (short)(value>>16);
	}
	code_000fab20(index, &random_vector);

	cross_product3d(axis, &random_vector, &perpendicular);

	if (normalize3d(&perpendicular)>0.0f)
	{
		real angle= real_seed_random_range(seed, inner_cone_angle, outer_cone_angle);

		rotate_vector_about_axis(result, &perpendicular, sine(angle), cosine(angle));
	}

	return result;
}

/* ---------- private code */
