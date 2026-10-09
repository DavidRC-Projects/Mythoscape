import bpy
c = bpy.data.hair_curves.new("hc")
c.add_curves([4]*3)
print(dir(c)[:80])
print([a.name for a in c.attributes])
import numpy as np
pos = np.random.rand(12*3).astype(np.float32)
c.position_data.foreach_set("vector", pos)
r = c.attributes.new("radius", 'FLOAT', 'POINT')
r.data.foreach_set("value", np.full(12, 0.001, np.float32))
o = bpy.data.objects.new("h", c); bpy.context.scene.collection.objects.link(o)
print("OK", len(c.points), o.type)
