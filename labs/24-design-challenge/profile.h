/* Exclusive accounting uses linear - driver; device-busy cycles come from RTL. */
#ifdef AIM_PROFILE
enum { P_LINEAR, P_DRIVER, P_NORM, P_ATTN, P_GELU, P_COUNT };
static unsigned profile[P_COUNT], profile_steps[8][P_COUNT];
#define PROFILE_START(name) const unsigned name = cycle_after(0)
#define PROFILE_END(name, bucket) profile[bucket] += cycle_after(0) - (name)
#else
#define PROFILE_START(name) ((void)0)
#define PROFILE_END(name, bucket) ((void)0)
#endif
