

from juniors_toolbox.utils.types import Vec3f


def chaikin_generate_q_point(p_1: Vec3f, p_2: Vec3f) -> Vec3f:
    "Generate Q point from Chaikin's algoritm"
    parsed_p1 = Vec3f(p_1.x * 0.75, p_1.y * 0.75, p_1.z * 0.75)
    parsed_p2 = Vec3f(p_2.x * 0.25, p_2.y * 0.25, p_1.z * 0.25)

    return Vec3f(parsed_p1.x + parsed_p2.x, parsed_p1.y + parsed_p2.y, parsed_p1.z + parsed_p2.z)


def chaikin_generate_r_point(p_1: Vec3f, p_2: Vec3f) -> Vec3f:
    "Generate Q point from Chaikin's algoritm"
    parsed_p1 = Vec3f(p_1.x * 0.25, p_1.y * 0.25, p_1.z * 0.25)
    parsed_p2 = Vec3f(p_2.x * 0.75, p_2.y * 0.75, p_1.z * 0.75)

    return Vec3f(parsed_p1.x + parsed_p2.x, parsed_p1.y + parsed_p2.y, parsed_p1.z + parsed_p2.z)


def chaikin_algorithm(points: list[Vec3f], iterations=1):
    "Curve creation algoritm"
    new_points = [points[0]]

    for i, _ in enumerate(points):
        if i + 1 < len(points):
            p_1 = points[i]
            p_2 = points[i + 1]

            q_point = chaikin_generate_q_point(p_1, p_2)
            r_point = chaikin_generate_r_point(p_1, p_2)

            new_points.append(q_point)
            new_points.append(r_point)
        else:
            new_points.append(points[i])

    if iterations == 1:
        return new_points
    return chaikin_algorithm(new_points, iterations - 1)