/*
 * Neo Geo native (M68K) lightweight 2D physics — host-exported scene + runtime API
 * used by transpiled neogeo-py (sim.step, sim.add_rigid_body, etc.). Strong symbols
 * here override weak stubs from js13k_neogeo_scripts.c.
 *
 * Collision: world AABBs rebuilt each step from OBB corners (rotation-aware broad
 * approximation; stable stacking for typical platformer shapes).
 */
#include <math.h>
#include <stdint.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define NEO_MAX_RB 48
#define NEO_MAX_COL 96
#define NEO_DT (1.0f / 60.0f)

typedef struct {
	float px, py, vx, vy, rot_deg, ang_vel;
	float gravity_scale;
	float linear_drag, angular_drag;
	float inv_mass, inv_inertia;
	int32_t enabled;
	int32_t body_type;
	int32_t can_rot;
} NeoBody;

typedef struct {
	int32_t body;
	float hw, hh;
	float lx, ly;
	float lrot_deg;
	float restitution;
	float density;
	int32_t enabled;
	int32_t sensor;
	uint32_t membership;
	uint32_t filter;
} NeoCollider;

/* Filled by generated prefix (js13k_neogeo_physics.c). */
extern const int neo_export_body_n;
extern const int neo_export_col_n;
extern const float neo_export_gravity[2];

typedef struct {
	float px, py, vx, vy, rot_deg, ang_vel, gs;
	int32_t enabled, body_type, can_rot;
	float lin_drag, ang_drag;
} NeoBodyInit;

typedef struct {
	int32_t body;
	float hw, hh, lx, ly, lrot_deg, rest, density;
	int32_t enabled, sensor;
	uint32_t membership, filter;
} NeoColInit;

extern const NeoBodyInit neo_export_bodies[];
extern const NeoColInit neo_export_cols[];

extern const int neo_rb_map_n;
typedef struct {
	const char *s;
	int32_t h;
} NeoRbNameEntry;
extern const NeoRbNameEntry neo_rb_map[];

/*JS13K_NEO_DATA*/

static NeoBody g_rb[NEO_MAX_RB];
static NeoCollider g_col[NEO_MAX_COL];
static int32_t g_rb_count;
static int32_t g_col_count;
static float g_len_unit = 1.0f;
static float g_gx, g_gy;
static int32_t g_pos_out[2];
static int32_t g_vel_out[2];

static int32_t neo_rb_valid (int32_t h)
{
	return h >= 1 && h <= g_rb_count;
}

static float neo_deg2rad (float d)
{
	return d * (float)M_PI / 180.0f;
}

static void neo_rot_vec (float x, float y, float rot_deg, float *ox, float *oy)
{
	float r = neo_deg2rad(rot_deg);
	float c = cosf(r);
	float s = sinf(r);
	*ox = c * x - s * y;
	*oy = s * x + c * y;
}

static void neo_col_world_obb (
	const NeoBody *b,
	const NeoCollider *c,
	float *cx,
	float *cy,
	float *rot_deg,
	float *hw,
	float *hh
)
{
	if (b == NULL)
	{
		*cx = c->lx;
		*cy = c->ly;
		*rot_deg = c->lrot_deg;
		*hw = c->hw;
		*hh = c->hh;
		return;
	}
	float ox, oy;
	neo_rot_vec(c->lx, c->ly, b->rot_deg, &ox, &oy);
	*cx = b->px + ox;
	*cy = b->py + oy;
	*rot_deg = b->rot_deg + c->lrot_deg;
	*hw = c->hw;
	*hh = c->hh;
}

static void neo_obb_aabb (
	float cx,
	float cy,
	float rot_deg,
	float hw,
	float hh,
	float *minx,
	float *maxx,
	float *miny,
	float *maxy
)
{
	float corners_x[4];
	float corners_y[4];
	float r = neo_deg2rad(rot_deg);
	float c = cosf(r);
	float s = sinf(r);
	float ax0 = c * hw;
	float ay0 = s * hw;
	float ax1 = -s * hh;
	float ay1 = c * hh;
	corners_x[0] = cx - ax0 - ax1;
	corners_y[0] = cy - ay0 - ay1;
	corners_x[1] = cx + ax0 - ax1;
	corners_y[1] = cy + ay0 - ay1;
	corners_x[2] = cx + ax0 + ax1;
	corners_y[2] = cy + ay0 + ay1;
	corners_x[3] = cx - ax0 + ax1;
	corners_y[3] = cy - ay0 + ay1;
	float mn_x = corners_x[0];
	float mx_x = corners_x[0];
	float mn_y = corners_y[0];
	float my_y = corners_y[0];
	int i;
	for (i = 1; i < 4; ++i)
	{
		if (corners_x[i] < mn_x)
			mn_x = corners_x[i];
		if (corners_x[i] > mx_x)
			mx_x = corners_x[i];
		if (corners_y[i] < mn_y)
			mn_y = corners_y[i];
		if (corners_y[i] > my_y)
			my_y = corners_y[i];
	}
	*minx = mn_x;
	*maxx = mx_x;
	*miny = mn_y;
	*maxy = my_y;
}

static int neo_groups_hit (uint32_t ma, uint32_t fa, uint32_t mb, uint32_t fb)
{
	/* All-zero masks: treat as default collide-all (matches common Blender "unset" groups). */
	if ((ma | fa | mb | fb) == 0u)
		return 1;
	return ((ma & fb) != 0u) && ((mb & fa) != 0u);
}

static float neo_fmin2 (float x, float y)
{
	return x < y ? x : y;
}

static float neo_fmax2 (float x, float y)
{
	return x > y ? x : y;
}

static void neo_resolve_aabb (
	NeoBody *a,
	float aminx,
	float amaxx,
	float aminy,
	float amaxy,
	float bminx,
	float bmaxx,
	float bminy,
	float bmaxy,
	float rest
)
{
	float ox = neo_fmin2(amaxx, bmaxx) - neo_fmax2(aminx, bminx);
	float oy = neo_fmin2(amaxy, bmaxy) - neo_fmax2(aminy, bminy);
	if (ox <= 0.0f || oy <= 0.0f)
		return;
	float nx, ny, pen;
	if (ox < oy)
	{
		pen = ox;
		nx = ((aminx + amaxx) * 0.5f < (bminx + bmaxx) * 0.5f) ? -1.0f : 1.0f;
		ny = 0.0f;
	}
	else
	{
		pen = oy;
		nx = 0.0f;
		ny = ((aminy + amaxy) * 0.5f < (bminy + bmaxy) * 0.5f) ? -1.0f : 1.0f;
	}
	if (pen <= 0.0f || a->inv_mass <= 0.0f)
		return;
	a->px += nx * pen * 0.5f;
	a->py += ny * pen * 0.5f;
	float vn = a->vx * nx + a->vy * ny;
	if (vn < 0.0f)
	{
		float impulse = -(1.0f + rest) * vn;
		a->vx += nx * impulse;
		a->vy += ny * impulse;
	}
}

void js13k_neogeo_physics_init (void)
{
	int i, ci;
	g_len_unit = 1.0f;
	g_gx = 0.0f;
	g_gy = -9.81f;
	g_rb_count = 0;
	g_col_count = 0;
	memset(g_rb, 0, sizeof(g_rb));
	memset(g_col, 0, sizeof(g_col));
	if (neo_export_gravity != NULL)
	{
		g_gx = neo_export_gravity[0];
		g_gy = neo_export_gravity[1];
	}
	if (neo_export_body_n > 0 && neo_export_bodies != NULL)
	{
		int n = neo_export_body_n;
		if (n > NEO_MAX_RB)
			n = NEO_MAX_RB;
		for (i = 0; i < n; ++i)
		{
			const NeoBodyInit *s = &neo_export_bodies[i];
			NeoBody *d = &g_rb[i];
			d->px = s->px;
			d->py = s->py;
			d->vx = s->vx;
			d->vy = s->vy;
			d->rot_deg = s->rot_deg;
			d->ang_vel = s->ang_vel;
			d->gravity_scale = s->gs;
			d->linear_drag = s->lin_drag;
			d->angular_drag = s->ang_drag;
			d->enabled = s->enabled;
			d->body_type = s->body_type;
			d->can_rot = s->can_rot;
			d->inv_mass = 0.0f;
			d->inv_inertia = 0.0f;
		}
		g_rb_count = n;
	}
	if (neo_export_col_n > 0 && neo_export_cols != NULL)
	{
		int m = neo_export_col_n;
		if (m > NEO_MAX_COL)
			m = NEO_MAX_COL;
		for (i = 0; i < m; ++i)
		{
			const NeoColInit *s = &neo_export_cols[i];
			NeoCollider *d = &g_col[i];
			d->body = s->body;
			d->hw = s->hw;
			d->hh = s->hh;
			d->lx = s->lx;
			d->ly = s->ly;
			d->lrot_deg = s->lrot_deg;
			d->restitution = s->rest;
			d->density = s->density;
			d->enabled = s->enabled;
			d->sensor = s->sensor;
			d->membership = s->membership;
			d->filter = s->filter;
		}
		g_col_count = m;
	}
	for (i = 0; i < g_rb_count; ++i)
	{
		NeoBody *b = &g_rb[i];
		if (!b->enabled)
			continue;
		if (b->body_type != 0)
		{
			b->inv_mass = 0.0f;
			b->inv_inertia = 0.0f;
			continue;
		}
		float mass = 0.0f;
		for (ci = 0; ci < g_col_count; ++ci)
		{
			const NeoCollider *c = &g_col[ci];
			if (c->body != (int32_t)(i + 1) || !c->enabled || c->sensor)
				continue;
			float area = (c->hw * 2.0f) * (c->hh * 2.0f);
			if (area < 1e-6f)
				continue;
			mass += area * (c->density > 1e-6f ? c->density : 1.0f);
		}
		if (mass < 1e-4f)
			mass = 1.0f;
		b->inv_mass = 1.0f / mass;
		if (!b->can_rot)
			b->inv_inertia = 0.0f;
		else
			b->inv_inertia = b->inv_mass / (mass + 1.0f);
	}
}

void sim_set_length_unit (int32_t u)
{
	float f = (float)u;
	if (f > 1e-6f)
		g_len_unit = f;
}

void sim_set_gravity (int32_t gx, int32_t gy)
{
	g_gx = (float)gx;
	g_gy = (float)gy;
}

/* Transpiled neogeo-py uses milligravity so small floats (e.g. -0.4) are not rounded to 0. */
void sim_set_gravity_milli (int32_t gx_milli, int32_t gy_milli)
{
	g_gx = (float)gx_milli * 0.001f;
	g_gy = (float)gy_milli * 0.001f;
}

void js13k_neogeo_physics_ensure_gravity_from_export (void)
{
	if (neo_export_gravity == NULL)
		return;
	if ((fabsf(g_gx) > 1e-5f) || (fabsf(g_gy) > 1e-5f))
		return;
	g_gx = neo_export_gravity[0];
	g_gy = neo_export_gravity[1];
}

int32_t sim_add_rigid_body (
	int32_t enabled,
	int32_t body_type,
	int32_t *pos,
	int32_t rot_deg,
	int32_t gravity_scale,
	int32_t dominance,
	int32_t can_rot,
	int32_t linear_drag,
	int32_t ang_drag,
	int32_t can_sleep,
	int32_t ccd
)
{
	(void)dominance;
	(void)can_sleep;
	(void)ccd;
	if (g_rb_count >= NEO_MAX_RB)
		return 0;
	if (pos == NULL)
		return 0;
	NeoBody *b = &g_rb[g_rb_count];
	memset(b, 0, sizeof(*b));
	b->enabled = enabled;
	b->body_type = body_type;
	b->px = (float)pos[0];
	b->py = (float)pos[1];
	b->rot_deg = (float)rot_deg;
	b->gravity_scale = (float)gravity_scale;
	b->can_rot = can_rot;
	b->linear_drag = (float)linear_drag / 100.0f;
	b->angular_drag = (float)ang_drag / 100.0f;
	if (body_type == 0)
		b->inv_mass = 1.0f / 1.0f;
	else
		b->inv_mass = 0.0f;
	++g_rb_count;
	return g_rb_count;
}

int32_t sim_add_cuboid_collider (
	int32_t enabled,
	int32_t *pos,
	int32_t rot_deg,
	int32_t membership,
	int32_t filter_mask,
	int32_t *size,
	int32_t is_sensor,
	int32_t density,
	int32_t bounciness,
	int32_t combine_rule,
	int32_t attach_rb
)
{
	(void)combine_rule;
	if (g_col_count >= NEO_MAX_COL)
		return 0;
	if (pos == NULL || size == NULL)
		return 0;
	NeoCollider *c = &g_col[g_col_count];
	memset(c, 0, sizeof(*c));
	c->enabled = enabled;
	c->sensor = is_sensor;
	c->membership = (uint32_t)membership;
	c->filter = (uint32_t)filter_mask;
	{
		float br = (float)bounciness;
		c->restitution = (br > 1.001f ? br * 0.01f : br);
		if (c->restitution < 0.0f)
			c->restitution = 0.0f;
		if (c->restitution > 1.0f)
			c->restitution = 1.0f;
	}
	c->density = (float)density / 100.0f;
	if (c->density < 1e-4f)
		c->density = 1e-4f;
	c->hw = (float)size[0] * 0.5f;
	c->hh = (float)size[1] * 0.5f;
	c->lrot_deg = 0.0f;
	if (attach_rb <= 0)
	{
		c->body = 0;
		c->lx = (float)pos[0];
		c->ly = (float)pos[1];
		c->lrot_deg = (float)rot_deg;
	}
	else
	{
		c->body = attach_rb;
		if (neo_rb_valid(attach_rb))
		{
			const NeoBody *b = &g_rb[attach_rb - 1];
			float wx = (float)pos[0];
			float wy = (float)pos[1];
			float lx, ly;
			neo_rot_vec(wx - b->px, wy - b->py, -b->rot_deg, &lx, &ly);
			c->lx = lx;
			c->ly = ly;
		}
		else
		{
			c->lx = 0.0f;
			c->ly = 0.0f;
		}
		c->lrot_deg = (float)rot_deg - (neo_rb_valid(attach_rb) ? g_rb[attach_rb - 1].rot_deg : 0.0f);
	}
	if (attach_rb > 0 && neo_rb_valid(attach_rb))
	{
		NeoBody *b = &g_rb[attach_rb - 1];
		float area = (c->hw * 2.0f) * (c->hh * 2.0f);
		if (b->body_type == 0)
			b->inv_mass = 1.0f / (area * c->density + 0.01f);
	}
	++g_col_count;
	return g_col_count;
}

int32_t *sim_get_rigid_body_position (int32_t rb)
{
	g_pos_out[0] = 0;
	g_pos_out[1] = 0;
	if (!neo_rb_valid(rb))
		return g_pos_out;
	const NeoBody *b = &g_rb[rb - 1];
	g_pos_out[0] = (int32_t)lroundf(b->px);
	g_pos_out[1] = (int32_t)lroundf(b->py);
	return g_pos_out;
}

/* main.c user-art sync: unrounded float pose so sub-pixel sim motion still moves sprites after rounding. */
void neo_rb_world_center_xy_f (int32_t rb, float *ox, float *oy)
{
	if (ox == NULL || oy == NULL)
		return;
	*ox = 0.0f;
	*oy = 0.0f;
	if (!neo_rb_valid(rb))
		return;
	const NeoBody *b = &g_rb[rb - 1];
	*ox = b->px;
	*oy = b->py;
}

int32_t sim_get_rigid_body_rotation (int32_t rb)
{
	if (!neo_rb_valid(rb))
		return 0;
	return (int32_t)lroundf(g_rb[rb - 1].rot_deg);
}

int32_t *sim_get_linear_velocity (int32_t rb)
{
	g_vel_out[0] = 0;
	g_vel_out[1] = 0;
	if (!neo_rb_valid(rb))
		return g_vel_out;
	const NeoBody *b = &g_rb[rb - 1];
	g_vel_out[0] = (int32_t)lroundf(b->vx);
	g_vel_out[1] = (int32_t)lroundf(b->vy);
	return g_vel_out;
}

void sim_set_linear_velocity (int32_t rb, int32_t *vel)
{
	if (!neo_rb_valid(rb) || vel == NULL)
		return;
	NeoBody *b = &g_rb[rb - 1];
	b->vx = (float)vel[0];
	b->vy = (float)vel[1];
}

void sim_step (void)
{
	int i, iter, ci, cj;
	for (i = 0; i < g_rb_count; ++i)
	{
		NeoBody *b = &g_rb[i];
		if (!b->enabled || b->body_type != 0 || b->inv_mass <= 0.0f)
			continue;
		b->vx += g_gx * b->gravity_scale * NEO_DT;
		b->vy += g_gy * b->gravity_scale * NEO_DT;
		if (b->linear_drag > 1e-6f)
		{
			/* Rapier-style damping per step; clamp so we never zero velocity in one frame. */
			float t = b->linear_drag * NEO_DT;
			if (t > 0.35f)
				t = 0.35f;
			b->vx *= (1.0f - t);
			b->vy *= (1.0f - t);
		}
		b->px += b->vx * NEO_DT;
		b->py += b->vy * NEO_DT;
		if (b->can_rot && b->inv_inertia > 0.0f)
		{
			if (b->angular_drag > 1e-6f)
			{
				float t = b->angular_drag * NEO_DT;
				if (t > 0.35f)
					t = 0.35f;
				b->ang_vel *= (1.0f - t);
			}
			b->rot_deg += b->ang_vel * NEO_DT;
		}
	}
	for (iter = 0; iter < 3; ++iter)
	{
		for (ci = 0; ci < g_col_count; ++ci)
		{
			NeoCollider *ca = &g_col[ci];
			if (!ca->enabled || ca->sensor)
				continue;
			const NeoBody *ba = (ca->body > 0) ? &g_rb[ca->body - 1] : NULL;
			if (ca->body > 0 && (ba == NULL || !ba->enabled))
				continue;
			float cax, cay, carot, cahw, cahh;
			neo_col_world_obb(ba, ca, &cax, &cay, &carot, &cahw, &cahh);
			float amin_x, amax_x, amin_y, amax_y;
			neo_obb_aabb(cax, cay, carot, cahw, cahh, &amin_x, &amax_x, &amin_y, &amax_y);
			for (cj = ci + 1; cj < g_col_count; ++cj)
			{
				NeoCollider *cb = &g_col[cj];
				if (!cb->enabled || cb->sensor)
					continue;
				if (!neo_groups_hit(ca->membership, ca->filter, cb->membership, cb->filter))
					continue;
				const NeoBody *bb = (cb->body > 0) ? &g_rb[cb->body - 1] : NULL;
				if (cb->body > 0 && (bb == NULL || !bb->enabled))
					continue;
				float cbx, cby, cbrot, cbhw, cbhh;
				neo_col_world_obb(bb, cb, &cbx, &cby, &cbrot, &cbhw, &cbhh);
				float bmin_x, bmax_x, bmin_y, bmax_y;
				neo_obb_aabb(cbx, cby, cbrot, cbhw, cbhh, &bmin_x, &bmax_x, &bmin_y, &bmax_y);
				int32_t da = (ba != NULL && ba->body_type == 0 && ba->inv_mass > 0.0f);
				int32_t db = (bb != NULL && bb->body_type == 0 && bb->inv_mass > 0.0f);
				if (!da && !db)
					continue;
				float rest = ca->restitution;
				if (cb->restitution > rest)
					rest = cb->restitution;
				if (da && !db)
					neo_resolve_aabb(&g_rb[ca->body - 1], amin_x, amax_x, amin_y, amax_y, bmin_x, bmax_x, bmin_y, bmax_y, rest);
				else if (!da && db)
					neo_resolve_aabb(&g_rb[cb->body - 1], bmin_x, bmax_x, bmin_y, bmax_y, amin_x, amax_x, amin_y, amax_y, rest);
				else
				{
					neo_resolve_aabb(&g_rb[ca->body - 1], amin_x, amax_x, amin_y, amax_y, bmin_x, bmax_x, bmin_y, bmax_y, rest);
					neo_resolve_aabb(&g_rb[cb->body - 1], bmin_x, bmax_x, bmin_y, bmax_y, amin_x, amax_x, amin_y, amax_y, rest);
				}
			}
		}
	}
}

void physics_step (void)
{
	sim_step();
}

int32_t get_rigidbody (const char *name)
{
	int i;
	if (name == NULL)
		return 0;
	for (i = 0; i < neo_rb_map_n; ++i)
	{
		if (neo_rb_map[i].s != NULL && strcmp(name, neo_rb_map[i].s) == 0)
			return neo_rb_map[i].h;
	}
	return 0;
}
