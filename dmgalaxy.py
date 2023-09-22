from direct.showbase.ShowBase import ShowBase
from panda3d.core import ShaderBuffer, GeomEnums, TextNode, load_prc_file_data, Vec4, NodePath, TextNode, Vec3, LColor, ComputeNode, Shader, Texture, ShaderAttrib, WindowProperties, Point3
from direct.task import Task
from direct.interval.IntervalGlobal import *
from direct.filter.CommonFilters import CommonFilters
import numpy as np
import sys, random
from array import array


class GalaxySimulation(ShowBase):
    def __init__(self):
        load_prc_file_data("", """
            win-size 1600 900
            window-title Galaxy Simulation
            framebuffer-multisample 1
            multisamples 4
        """)

        super().__init__()

        self.size = 20
        self.dark_matter_factor = 1.0
        self.mass_factor = 1000
        self.force_reduction_factor = 5.0
        win_props = WindowProperties.size(self.win.get_x_size(), self.win.get_y_size())
        base.win.request_properties(win_props)
        base.set_background_color(Vec4(0,0,0,1))
        self.grid = np.zeros((self.size, self.size, self.size), dtype=np.float32)
        # self.init_grid()
        self.init_grid_spiral()
        self.create_geometry()

        self.positionTex = Texture("positions")
        self.positionTex.setup_3d_texture(self.size, self.size, self.size, Texture.T_float, Texture.F_rgba32)
        self.positionTex.clear_image()
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
        self.final_compute_shader.set_shader_input("outputTexture", self.outputTex)

        # set up the velocity SSBO
        # num_particles = int(self.size*self.size*self.size * 0.1)
        # data_list = np.zeros((num_particles, 3), dtype=np.float32)
        '''
        data_list = [1.,1.,1.]
        initial_data = array('f', data_list)
        shader_buffer_1 = ShaderBuffer('velocity_data', initial_data.tobytes(), GeomEnums.UH_static)
        self.final_compute_shader.set_shader_input("velocity_data", shader_buffer_1)
        '''
        num_particles = self.size * self.size * self.size
        data_list = np.zeros((num_particles, 3), dtype=np.float32).flatten().tolist()
        initial_data = array('f', data_list)
        shader_buffer_1 = ShaderBuffer('velocity_data', initial_data.tobytes(), GeomEnums.UH_static)
        self.final_compute_shader.set_shader_input("velocity_data", shader_buffer_1)
        
        self.task_mgr.add(self.update, "Update")
        self.cam.set_pos(40, 40, 40)
        self.cam.look_at(0,0,0)
        self.accept("escape", sys.exit)
        
        self.check_grid = []
        self.total_steps = 0

        scene_filters = CommonFilters(base.win, base.cam)
        scene_filters.set_bloom(size='medium')
        scene_filters.set_exposure_adjust(1.1)
        scene_filters.set_gamma_adjust(1.1)
        scene_filters.set_blur_sharpen(0.25)

        self.menu_items()
        self.accept('arrow_up', self.increase_dark_matter)
        self.accept('arrow_down', self.decrease_dark_matter)
        self.accept('arrow_right', self.increase_mass)
        self.accept('arrow_left', self.decrease_mass)
        self.arrow_text_1 = "arrow up/down \n" + "dark matter factor: "
        self.arrow_text_2 = "\n\narrow left/right \n" + "mass factor: "
        self.zoom_text = "\n\n1 to zoom out\n2 to zoom in\n\n" + "3 to reduce force\n" + "4 to increase force\n"
        self.accept('1', self.zoom_in)
        self.accept('2', self.zoom_out)
        self.accept('3', self.increase_force_reduction)
        self.accept('4', self.decrease_force_reduction)

    def menu_items(self):
        self.text_1 = TextNode('text_1_node')
        self.text_1.set_text('')
        self.text_1_node = self.aspect2d.attach_new_node(self.text_1)
        self.text_1_node.set_scale(0.04)
        self.text_1_node.set_pos(-1.4, 0, 0.92)
        nunito_font = loader.load_font('fonts/Nunito/Nunito-Light.ttf')
        nunito_font.set_pixels_per_unit(100)
        nunito_font.set_page_size(512, 512)
        self.text_1.set_font(nunito_font)

    def zoom_in(self):
        self.camLens.set_focal_length(self.camLens.get_focal_length() - 0.2)

    def zoom_out(self):
        self.camLens.set_focal_length(self.camLens.get_focal_length() + 0.2)

    def increase_force_reduction(self):
        self.force_reduction_factor += 1.0

    def decrease_force_reduction(self):
        self.force_reduction_factor -= 1.0
        if self.force_reduction_factor <= 0: self.force_reduction_factor = 1.0

    def increase_mass(self):
        self.mass_factor += 100.0

    def decrease_mass(self):
        self.mass_factor -= 100.0
        if self.mass_factor <= 0: self.mass_factor = 0.001

    def increase_dark_matter(self):
        self.dark_matter_factor += 0.5

    def decrease_dark_matter(self):
        self.dark_matter_factor -= 0.5
        if self.dark_matter_factor <= 0: self.dark_matter_factor = 0.001

    def create_geometry(self):
        self.cube_model = self.loader.load_model("1m_cube.gltf")
        self.cube_model.set_scale(0.02)
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

    def init_grid_spiral(self, sparsity=0.1, arm_sparsity=0.5):
        # generate a smaller number of particles based on sparsity value
        center_mass_particles = int(self.size * self.size * self.size * sparsity)
        arm_particles = int(self.size * self.size * self.size * arm_sparsity)
            
        # generate uniform random particles for center mass
        center_positions = np.random.rand(center_mass_particles, 3) * self.size
        center_velocities = np.zeros((center_mass_particles, 3), dtype=np.float32)
        
        # generate particles in spiral arms
        R = self.size / 2 # radius of arms
        arm_positions = []
        
        for _ in range(arm_particles):
            # choose random spiral arm
            theta = 2. * np.pi * np.random.rand()
            z = (np.random.rand() - 0.5) * self.size
            if np.random.rand() > 0.5:
                x = R * np.cos(theta) + R
                y = R * np.sin(theta) + R
            else:
                x = R * np.cos(theta + np.pi) + R
                y = R * np.sin(theta + np.pi) + R
            arm_positions.append([x, y, z])
            
        arm_positions = np.array(arm_positions)
        arm_velocities = np.zeros((arm_particles, 3), dtype=np.float32)
        
        # combine particle arrays
        particle_positions = np.concatenate((center_positions, arm_positions), axis=0)
        particle_velocities = np.concatenate((center_velocities, arm_velocities), axis=0)
        num_particles = len(particle_positions)
            
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
        self.text_1.set_text(self.arrow_text_1 + str(round(self.dark_matter_factor, 2)) + self.arrow_text_2 +
                             str(round(self.mass_factor, 2)) + self.zoom_text + 'FRF: ' + str(round(self.force_reduction_factor, 2)))
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

        self.final_compute_shader.set_shader_input("positionTexture", self.positionTex)
        self.final_compute_shader.set_shader_input("darkMatterFactor", self.dark_matter_factor)
        self.final_compute_shader.set_shader_input("massFactor", self.mass_factor)
        self.final_compute_shader.set_shader_input("forceReductionFactor", self.force_reduction_factor)

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
                            self.cube_model.instance_to(instance)
                            instance.set_pos(Point3(*output_array[x, y, z, :3]))
                            # seq = Sequence()
                            # inter = LerpPosInterval(instance, 1, Point3(*output_array[x, y, z, :3]))
                            # seq.append(inter)
                            # seq.start()
                    else:
                        self.grid[x][y][z] = 0
        
        # base.cam.look_at((self.size/2, self.size/2, self.size/2))
        self.total_steps += 1
        # base.win.save_screenshot('galaxy_sim_' + str(self.total_steps) + '.png')

        # task.delay_time = 1
        # return task.again
        return task.cont


base = GalaxySimulation()
base.run()
