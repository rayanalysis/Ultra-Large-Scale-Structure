from direct.showbase.ShowBase import ShowBase
from panda3d.core import load_prc_file_data, NodePath, TextNode, Vec3, LColor, ComputeNode, Shader, Texture, ShaderAttrib, WindowProperties, Point3
from direct.task import Task
import numpy as np
import sys, random


class GalaxySimulation(ShowBase):
    def __init__(self):
        load_prc_file_data("", """
            win-size 900 600
            window-title Galaxy Simulation
        """)

        super().__init__()

        self.size = 20
        self.dark_matter_factor = 1.0
        win_props = WindowProperties.size(self.win.get_x_size(), self.win.get_y_size())
        # win_props.set_origin(100, 100)
        base.win.request_properties(win_props)
        self.grid = np.zeros((self.size, self.size, self.size), dtype=np.float32)
        self.init_grid()
        self.create_geometry()

        self.positionTex = Texture("positions")
        self.positionTex.setup_3d_texture(self.size, self.size, self.size, Texture.T_float, Texture.F_rgba32)
        self.positionTex.clear_image()
        self.velocityTex = Texture("velocities")
        self.velocityTex.setup_3d_texture(self.size, self.size, self.size, Texture.T_float, Texture.F_rgba32)
        self.velocityTex.clear_image()
        self.outputVelTex = Texture("outputVelocities")
        self.outputVelTex.setup_3d_texture(self.size, self.size, self.size, Texture.T_float, Texture.F_rgba32)
        self.outputVelTex.clear_image()
        
        self.outputTex = Texture("output")
        self.outputTex.setup_3d_texture(self.size, self.size, self.size, Texture.T_float, Texture.F_rgba32)
        self.outputTex.clear_image()
        
        shader = Shader.load_compute(Shader.SL_GLSL, "galaxy_compute.glsl")
        self.compute_node_path = ComputeNode("compute")
        self.compute_node_path.add_dispatch(self.size, self.size, self.size)
        self.final_compute_shader = self.render.attach_new_node(self.compute_node_path)
        self.final_compute_shader.set_shader(shader)
        self.final_compute_shader.set_shader_input("size", self.size)
        self.final_compute_shader.set_shader_input("positionTexture", self.positionTex)
        self.final_compute_shader.set_shader_input("velocityTexture", self.velocityTex)
        self.final_compute_shader.set_shader_input("outputTexture", self.outputTex)
        self.final_compute_shader.set_shader_input("outputVelTexture", self.outputVelTex)
        
        self.task_mgr.add(self.update, "Update")
        self.cam.set_pos(100, 200, 50)
        self.cam.look_at(0,0,0)
        self.accept("escape", sys.exit)
        self.accept('arrow_up', self.increase_dark_matter)
        self.accept('arrow_down', self.decrease_dark_matter)
        self.accept('space', self.toggle_dark_matter)

        self.check_grid = []
        self.total_steps = 0

    def increase_dark_matter(self):
        self.dark_matter_factor += 0.1

    def decrease_dark_matter(self):
        self.dark_matter_factor -= 0.1
        if self.dark_matter_factor < 0: self.dark_matter_factor = 0

    def toggle_dark_matter(self):
        self.dark_matter_factor = self.dark_matter_factor == 0 and 1 or 0

    def create_geometry(self):
        self.cube_model = self.loader.load_model("1m_cube.gltf")
        self.cube_model.set_scale(0.1)
        self.cube_model.set_name("CubeModel")

        self.instance_root = NodePath("InstanceRoot")
        self.instance_root.reparent_to(self.render)

        for x in range(self.size):
            for y in range(self.size):
                for z in range(self.size):
                    if self.grid[x][y][z]:
                        instance = self.instance_root.attach_new_node("Instance")
                        instance.set_pos(Point3(x, y, z))
                        self.cube_model.instance_to(instance)

    def init_grid(self, sparsity=0.1):
        # generate a smaller number of particles based on sparsity value
        num_particles = int(self.size*self.size*self.size * sparsity)
        particle_positions = np.random.rand(num_particles, 3) * self.size
        particle_velocities = np.zeros((num_particles, 3), dtype=np.float32)
        
        # initialize every cell in the grid with default values (no particles initially)
        self.grid = [[[ [ [0,0,0], [0,0,0] ] for _ in range(self.size)] for _ in range(self.size)] for _ in range(self.size)]

        # populate the grid with given positions and velocities
        for i in range(num_particles):
            x, y, z = particle_positions[i].astype(int)
            x, y, z = np.clip([x, y, z], 0, self.size-1)  # ensure x, y, z are within valid index ranges
            self.grid[x][y][z] = [particle_positions[i].tolist(), particle_velocities[i].tolist()]

        print(self.grid, '<-- that is the starting grid.')
        self.check_grid = self.grid
        
    def update(self, task):
        new_grid_positions = []
        new_grid_velocities = []
        # print(self.grid, '<-- that is self.grid')
        for x in range(self.size):
            for y in range(self.size):
                for z in range(self.size):
                    if self.grid[x][y][z] is not None:
                        new_grid_positions.extend(self.grid[x][y][z][0])
                        new_grid_velocities.extend(self.grid[x][y][z][1])
                        

        new_grid_positions = np.array(new_grid_positions, dtype=np.float32)
        new_grid_velocities = np.array(new_grid_velocities, dtype=np.float32)
        # print(new_grid_positions[0])

        PTA_uchar_positions = self.positionTex.modify_ram_image()
        pta_np_positions = np.frombuffer(PTA_uchar_positions, dtype=np.float32)
        np.copyto(pta_np_positions[:len(new_grid_positions)], new_grid_positions)

        PTA_uchar_velocities = self.velocityTex.modify_ram_image()
        pta_np_velocities = np.frombuffer(PTA_uchar_velocities, dtype=np.float32)
        np.copyto(pta_np_velocities[:len(new_grid_velocities)], new_grid_velocities)

        self.final_compute_shader.set_shader_input("positionTexture", self.positionTex)
        self.final_compute_shader.set_shader_input("velocityTexture", self.velocityTex)
        self.final_compute_shader.set_shader_input("darkMatterFactor", self.dark_matter_factor)

        compute_attrib = self.final_compute_shader.get_attrib(ShaderAttrib)
        base.graphicsEngine.dispatch_compute((self.size, self.size, self.size), compute_attrib, base.win.get_gsg())
        # self.final_compute_shader.set_shader_input("darkMatterFactor", self.dark_matter_factor)  # resetting dark_matter_factor uniform
        base.graphics_engine.extract_texture_data(self.outputTex, base.win.get_gsg())

        output_data = memoryview(self.outputTex.get_ram_image_as('RGBA')).cast("B").cast("f")
        output_array = np.frombuffer(output_data, dtype=np.float32)
        # print(output_array.shape, '<-- the output_array shape.')
        output_array = output_array.reshape(self.size, self.size, self.size, 4)
        # print(output_array.shape, '<-- the output_array shape.')
                
        for x in range(self.size):
            for y in range(self.size):
                for z in range(self.size):
                    self.grid[x][y][z] = [output_array[x, y, z, :3].tolist(), output_array[x, y, z, 3:].tolist()]

        # print(self.grid, '<-- the self.grid')
        # print(self.check_grid, '<-- the self.check_grid')
        # print(str(self.grid[0])[0:20], '<-- the self.grid first slice.')

        # update the geometry based on the new grid
        self.instance_root.remove_node()
        self.instance_root = NodePath("InstanceRoot")
        self.instance_root.reparent_to(self.render)

        for x in range(self.size):
            for y in range(self.size):
                for z in range(self.size):
                    # some_ranvar = random.randint(0,1)
                    some_ranvar = 1
                    if some_ranvar > 0.5:
                        current_position = output_array[x, y, z, :3] # get the position from the output_array
                        if not (np.isnan(output_array[x, y, z, :3]).any() or np.isinf(output_array[x, y, z, :3]).any()): 
                            self.grid[x][y][z] = [output_array[x, y, z, :3].tolist(), output_array[x, y, z, 3:].tolist()]
                            instance = self.instance_root.attach_new_node("Instance")
                            instance.set_pos(Point3(*output_array[x, y, z, :3]))
                            self.cube_model.instance_to(instance)
                    else:
                        self.grid[x][y][z] = 0
        
        base.cam.look_at((self.size/2, self.size/2, self.size/2))
        self.total_steps += 1
        # base.win.save_screenshot('galaxy_sim_' + str(self.total_steps) + '.png')

        # task.delay_time = 0.01
        # return task.again
        return task.cont


base = GalaxySimulation()
base.run()
