#version 430

struct Particle {
    vec4 pos_vel; // positions = vec3(pos_vel), velocity = pos_vel.w
};

layout(local_size_x = 1, local_size_y = 1, local_size_z = 1) in;
uniform int size;
uniform float darkMatterFactor;  // new uniform variable for dark matter factor.

uniform sampler3D positionTexture; // particle positions and velocities
layout(rgba32f) uniform image3D outputTexture; // Output positions 

uniform sampler3D velocityTexture; // particle velocities
layout(rgba32f) uniform image3D outputVelTexture; // output velocities

vec3 computeForce(vec3 pos, int index) {
    vec3 force = vec3(0.0, 0.0, 0.0);
    float mass = texelFetch(positionTexture, ivec3(pos), 0).w;

    for(int x = 0; x < size; ++x){
        for(int y = 0; y < size; ++y){
            for(int z = 0; z < size; ++z){
                if(x != index || y != index || z != index) {
                    vec3 otherPos = texelFetch(positionTexture, ivec3(x, y, z), 0).xyz;
                    float otherMass = texelFetch(positionTexture, ivec3(x, y, z), 0).w;
                    otherMass += darkMatterFactor * otherMass; // adding dark matter mass.

                    vec3 r = otherPos - pos;
                    float dist = length(r) + 0.1; // to prevent division by zero
                    vec3 forceDir = normalize(r);
                    float forceMag = mass * otherMass / (dist * dist); // correct value of G here.
                    force += forceMag * forceDir;
                }
            }
        } 
    }   
    return force;
}

void main() {
    ivec3 index = ivec3(gl_GlobalInvocationID.xyz);
    vec3 pos = texelFetch(positionTexture, index, 0).xyz;
    vec3 vel = texelFetch(velocityTexture, index, 0).xyz;

    vec3 force = computeForce(pos, int(gl_GlobalInvocationID.x));
    float mass = texelFetch(positionTexture, index, 0).w;
    mass += darkMatterFactor * mass; // adding dark matter mass.
    vec3 acc = force / mass;

    vec3 newVel = vel + acc; 
    vec3 newPos = pos + newVel;

    imageStore(outputVelTexture, index, vec4(newVel, 0.0));
    imageStore(outputTexture, index, vec4(newPos, mass)); // storing the original mass without Dark Matter.
}