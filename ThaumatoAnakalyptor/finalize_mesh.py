### Julian Schilliger - ThaumatoAnakalyptor - Vesuvius Challenge 2023

import open3d as o3d
import numpy as np
import argparse
import os
from PIL import Image
# max image size None
Image.MAX_IMAGE_PIXELS = None

def load_obj(path: str, delauny=False) -> o3d.geometry.TriangleMesh:
    """
    Load an .obj file and return the TriangleMesh object.
    """
    mesh = o3d.io.read_triangle_mesh(path)

    # png 
    path_png = path[:-4] + "_0.png"
    if delauny:
        path_png = path_png.replace("delauny", "uv")
    texture = Image.open(path_png)

    # Get the size of the image from disk
    texture_size = np.array(texture.size)
    return mesh, texture_size

def create_mtl_file(mtl_path, texture_image_name):
    texture_image_name = texture_image_name.split(".")[0] + "_0." + texture_image_name.split(".")[-1]
    content = f"""# Material file generated by ThaumatoAnakalyptor
    newmtl default
    Ka 1.0 1.0 1.0
    Kd 1.0 1.0 1.0
    Ks 0.0 0.0 0.0
    illum 2
    d 1.0
    map_Kd {texture_image_name}
    """

    with open(mtl_path, 'w') as file:
        file.write(content)

def save_obj_(path: str, mesh: o3d.geometry.TriangleMesh):
    """
    Save a TriangleMesh object with UV coordinates to an .obj file.
    
    Args:
        path (str): The path to save the .obj file.
        mesh (o3d.geometry.TriangleMesh): The mesh to save.
    """
    # make folder if not exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Save the mesh to an .obj file
    o3d.io.write_triangle_mesh(path, mesh)
    create_mtl_file(path.replace("obj", "mtl"), path.split("/")[-1].split(".")[0] + ".png")

def save_mesh(path, mesh, size_texture):
    save_obj_(path, mesh)
    # png 
    path_png = path[:-4] + "_0.png"
    # This disables the decompression bomb protection in Pillow
    Image.MAX_IMAGE_PIXELS = None

    # Create a grayscale image with a specified size
    n, m = int(np.ceil(size_texture[0])), int(np.ceil(size_texture[1]))  # replace with your dimensions
    image = Image.new('L', (n, m), color=255)  # 255 for white background, 0 for black

    # Save the image
    image.save(path_png)

def scale_mesh(mesh, scale_factor):
    # Scale the mesh by a given factor
    vertices = np.asarray(mesh.vertices)
    vertices *= scale_factor
    mesh.vertices = o3d.utility.Vector3dVector(vertices)
    return mesh

def normalize_uv_coordinates(uvs):
    # Normalize the UV coordinates between (0, 0) and (1, 1)
    uvs -= np.min(uvs, axis=0)
    max_uv = np.max(uvs, axis=0)
    if not np.all(max_uv == 0):  # Prevent division by zero
        uvs /= max_uv
    return uvs

def cut_mesh_size(mesh, texture_size, min_x, cut_size):
    """
    Cut a mesh into pieces along the x-axis
    cut size in frame of texture
    """
    max_x = min_x + cut_size

    texture_size = np.array(texture_size)
    # Uv of the texture
    uvs = np.asarray(mesh.triangle_uvs)
    uv_scaled = uvs * texture_size

    print(f"Number uvs: {len(uv_scaled)}")

    # Function to cut the mesh into pieces along the x-axis
    vertices = np.asarray(mesh.vertices)
    normals = np.asarray(mesh.vertex_normals)
    triangles = np.asarray(mesh.triangles)
    
    # Create a mask for vertices within the specified x range
    uvs_mask_ = (uv_scaled[:, 0] >= min_x) & (uv_scaled[:, 0] <= max_x)
    triangles_mask = uvs_mask_.reshape(-1, 3)
    print(f"Sum of triangles mask: {np.sum(triangles_mask)}, with shape {triangles_mask.shape}")
    # Select vertices and triangles within the x range
    triangles_mask = np.all(triangles_mask, axis=1)
    uvs_mask = triangles_mask.repeat(3).reshape(-1)

    selected_uvs = uv_scaled[uvs_mask]
    selected_triangles = triangles[triangles_mask]

    # Create a new mesh with the selected vertices and triangles
    cut_mesh = o3d.geometry.TriangleMesh()
    cut_mesh.vertices = o3d.utility.Vector3dVector(vertices)
    cut_mesh.vertex_normals = o3d.utility.Vector3dVector(normals)
    cut_mesh.triangles = o3d.utility.Vector3iVector(selected_triangles)
    cut_mesh.triangle_uvs = o3d.utility.Vector2dVector(selected_uvs)
    cut_mesh = cut_mesh.remove_unreferenced_vertices()

    # white tif of size 1x1
    tif = np.ones((int(np.ceil(1)), int(np.ceil(1)), 3), dtype=np.uint8)
    
    # Convert the numpy array to an Open3D Image and assign it as the mesh texture
    texture = o3d.geometry.Image(tif)
    cut_mesh.textures = [texture]

    cut_mesh_texture_size = np.array([np.max(selected_uvs[:,0]) - np.min(selected_uvs[:,0]), np.max(selected_uvs[:,1]) - np.min(selected_uvs[:,1])])

    print(f"Cut mesh from {min_x} to {max_x} with texture size {cut_mesh_texture_size[0]} to {cut_mesh_texture_size[1]} along the x-axis with {len(np.asarray(cut_mesh.vertices))} vertices and {len(np.asarray(cut_mesh.triangles))} triangles")
    return cut_mesh, cut_mesh_texture_size

def cut_meshes(mesh, texture_size, cut_size):
    # Calculate min and max x from the mesh
    min_x = 0.0
    max_x = texture_size[0]

    cut_meshes = []
    current_min_x = min_x

    total_vertices = len(np.asarray(mesh.vertices))
    print(f"Total vertices in mesh: {total_vertices}")
    total_cut_vertices = 0

    while current_min_x < max_x:
        # Cut the mesh
        cut_mesh, cut_mesh_texture_size = cut_mesh_size(mesh, texture_size, current_min_x, cut_size)
        if not cut_mesh.is_empty():
            # Normalize UV coordinates of the cut mesh
            if cut_mesh.has_triangle_uvs():
                uvs = np.asarray(cut_mesh.triangle_uvs)
                uvs = normalize_uv_coordinates(uvs)
                cut_mesh.triangle_uvs = o3d.utility.Vector2dVector(uvs)
            cut_meshes.append([cut_mesh, cut_mesh_texture_size])

        current_min_x += cut_size
        total_cut_vertices += len(np.asarray(cut_mesh.vertices))
    
    print(f"Cut mesh into {len(cut_meshes)} pieces with {total_cut_vertices} vertices out of {total_vertices} vertices in the original mesh")

    return cut_meshes

def save_cut(i, output_filename, cut_mesh, cut_mesh_texture_size):
    if not os.path.exists(os.path.dirname(output_filename)):
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    layers_path = os.path.dirname(output_filename) + "/layers"
    if not os.path.exists(layers_path):
        os.makedirs(layers_path, exist_ok=True)
    # Save mesh
    save_mesh(output_filename, cut_mesh, cut_mesh_texture_size)

    print(f"Saved cut mesh piece {i} to {output_filename}")

def main(args):
    output_folder = args.output_folder if args.output_folder is not None else "/".join(os.path.dirname(args.input_mesh).split("/")[:-1]) + "/working"
    # Ensure output directory exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Load mesh
    mesh, texture_size = load_obj(args.input_mesh, args.delauny)
    mesh_filename = os.path.basename(args.input_mesh)

    # Scale mesh
    mesh = scale_mesh(mesh, args.scale_factor)
    texture_size = (texture_size * args.scale_factor).astype(np.int32)

    # Cut mesh into pieces and normalize UVs
    cut_mesh_list = cut_meshes(mesh, texture_size, args.cut_size)

    # Save each cut piece and adjust the texture if necessary
    for i, (cut_mesh, cut_mesh_texture_size) in enumerate(cut_mesh_list):
        start_point = args.input_mesh.split("/")[-2]
        working_folder = f"working_{start_point}" + (f"_{i}" if i > 0 else "")
        output_filename = os.path.join(output_folder, working_folder, f"{mesh_filename.split('.')[0]}.obj")
        save_cut(i, output_filename, cut_mesh, cut_mesh_texture_size)
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scale and cut a mesh into pieces, normalize UVs, and handle textures")
    parser.add_argument("--input_mesh", type=str, required=True, help="Path to the input mesh file")
    parser.add_argument("--scale_factor", type=float, help="Scaling factor for vertices", default=2.0)
    parser.add_argument("--cut_size", type=float, help="Size of each cut piece along the X axis", default=20000.0)
    parser.add_argument("--delauny", action="store_true", help="Use Delauny triangulation")
    parser.add_argument("--output_folder", type=str, help="Folder to save the cut meshes", default=None)

    args = parser.parse_args()
    main(args)

# python3 finalize_mesh.py --input_mesh /media/julian/SSD4TB/scroll3_surface_points/<start_point_location>/point_cloud_colorized_verso_subvolume_blocks_uv.obj