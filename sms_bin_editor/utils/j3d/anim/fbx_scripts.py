
from fbx import *
import fbx as fbx

KFCURVE_INTERPOLATION_CONSTANT    = 0x00000002     
KFCURVE_INTERPOLATION_LINEAR      = 0x00000004     
KFCURVE_INTERPOLATION_CUBIC       = 0x00000008     


def import_fbx_file(filepath):
    import animations.bck as bck
    from animations.general_animation import AnimComponent
    
    manager = fbx.FbxManager.Create()
    importer = fbx.FbxImporter.Create(manager, "wheel")
    status = importer.Initialize(filepath)
    if status == False:
        print("couldn't find file")
    scene = fbx.FbxScene.Create(manager, "scene")
    node = scene.GetRootNode()
    importer.Import(scene)
    importer.Destroy()

    animations = [] #array of bcks
    base_pose = []
    
    stackcount = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))
    for i in range(stackcount):
        stack = scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i)

        bck_anim_info = DisplayLayers( stack, node)
        if bck_anim_info:           
            animations.append( [stack.GetName(), bck_anim_info] )
    
    DisplayRootNode(node, base_pose)
    for i in range(node.GetChildCount()):
        DisplayNodeHierarchy(node.GetChild(i), base_pose)
    
    for [name, bck] in animations: #for each animation
        for j in range( len( bck.animations ) ): # for each bone_anim
            print(base_pose[j])
            if len(bck.animations[j].scale["X"]) == 0:             
                anim_comp = AnimComponent(0, base_pose[j][0][0])
                bck.animations[j].scale["X"].append(anim_comp)
            if len(bck.animations[j].scale["Y"]) == 0:            
                anim_comp = AnimComponent(0, base_pose[j][0][1])
                bck.animations[j].scale["Y"].append(anim_comp)
            if len(bck.animations[j].scale["Z"]) == 0:            
                anim_comp = AnimComponent(0, base_pose[j][0][2])
                bck.animations[j].scale["Z"].append(anim_comp)
                
            if len(bck.animations[j].rotation["X"]) == 0:             
                anim_comp = AnimComponent(0, base_pose[j][1][0])
                bck.animations[j].rotation["X"].append(anim_comp)
            if len(bck.animations[j].rotation["Y"]) == 0:            
                anim_comp = AnimComponent(0, base_pose[j][1][1])
                bck.animations[j].rotation["Y"].append(anim_comp)
            if len(bck.animations[j].rotation["Z"]) == 0:            
                anim_comp = AnimComponent(0, base_pose[j][1][2])
                bck.animations[j].rotation["Z"].append(anim_comp)
                
            if len(bck.animations[j].translation["X"]) == 0:             
                anim_comp = AnimComponent(0, base_pose[j][2][0])
                bck.animations[j].translation["X"].append(anim_comp)
            if len(bck.animations[j].translation["Y"]) == 0:            
                anim_comp = AnimComponent(0, base_pose[j][2][1])
                bck.animations[j].translation["Y"].append(anim_comp)
            if len(bck.animations[j].translation["Z"]) == 0:            
                anim_comp = AnimComponent(0, base_pose[j][2][2])
                bck.animations[j].translation["Z"].append(anim_comp)
    
    return animations

#returns a full ass bck animation to be appended to the array of bcks
def DisplayLayers(stack, node):
    import animations.bck as bck
    bck_anim = bck.bck()
    
    duration = 0
    anglescale = 0
    
    # a layer is a bone
    layercount = stack.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimLayer.ClassId))
    for j in range(layercount): 
        layer = stack.GetSrcObject(FbxCriteria.ObjectType(FbxAnimLayer.ClassId), j)
        
        (bone_anim, maxs) = DisplayChannels(node, layer)
        bone_anim.name = node.GetName()
        bck_anim.animations.append(bone_anim)
        duration = max(duration, maxs[0] )
        anglescale = max(anglescale, maxs[1] )
                
        for lModelCount in range(node.GetChildCount()):
            maxs = DisplayAnimationLayer(layer, node.GetChild(lModelCount), bck_anim)
            duration = max(duration, maxs[0] )
            anglescale = max(anglescale, maxs[1] )
    
    bck_anim.duration = duration
    bck_anim.anglescale = anglescale
    
    return bck_anim

#will append a bone anim AT EACH CALL TO DISPLAY CHANNELS
def DisplayAnimationLayer(pAnimLayer, pNode, bck_anim):
    (bone_anim, maxs) = DisplayChannels(pNode, pAnimLayer)
    info = [maxs[0], maxs[1]]
    bone_anim.name = pNode.GetName()
    bck_anim.animations.append(bone_anim)
    
    for lModelCount in range(pNode.GetChildCount()):
        new_max = DisplayAnimationLayer(pAnimLayer, pNode.GetChild(lModelCount), bck_anim)
        info = [ max(maxs[0], new_max[0]), max(maxs[1], new_max[1]) ]
        
    return info
    
#returns a bone anim, to be appended to a bck's animations array
def DisplayChannels(pNode, pAnimLayer):
    import animations.bck as bck
    
    lAnimCurve = None
    duration = 0
    anglescale = 0
    bone_anim = bck.bone_anim()
    #bone_anim.name = pNode.GetName()
    # for each bone, get all the values
    lAnimCurve = pNode.LclTranslation.GetCurve(pAnimLayer, "X")
    if lAnimCurve:
        #print("        TX")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.translation, "X")
        duration = max(duration, dur)   
        bone_anim.tan_inter[6] = tan
    lAnimCurve = pNode.LclTranslation.GetCurve(pAnimLayer, "Y")
    if lAnimCurve:
        #print("        TY")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.translation, "Y")
        duration = max(duration, dur)
        bone_anim.tan_inter[7] = tan
    lAnimCurve = pNode.LclTranslation.GetCurve(pAnimLayer, "Z")
    if lAnimCurve:
        #print("        TZ")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.translation, "Z")
        duration = max(duration, dur)
        bone_anim.tan_inter[8] = tan
    lAnimCurve = pNode.LclRotation.GetCurve(pAnimLayer, "X")
    if lAnimCurve:
        #print("        RX")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.rotation, "X")
        duration = max(duration, dur)
        anglescale = max( anglescale, int( ang / 180) )
        bone_anim.tan_inter[3] = tan
    lAnimCurve = pNode.LclRotation.GetCurve(pAnimLayer, "Y")
    if lAnimCurve:
        #print("        RY")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.rotation, "Y")
        duration = max(duration, dur)
        anglescale = max( anglescale, int( ang / 180) )
        bone_anim.tan_inter[4] = tan
    lAnimCurve = pNode.LclRotation.GetCurve(pAnimLayer, "Z")
    if lAnimCurve:
        #print("        RZ")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.rotation, "Z")
        duration = max(duration, dur)
        anglescale = max( anglescale, int( ang / 180) )
        bone_anim.tan_inter[5] = tan
    lAnimCurve = pNode.LclScaling.GetCurve(pAnimLayer, "X")
    if lAnimCurve:
        #print("        SX")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.scale, "X")
        duration = max(duration, dur)
        bone_anim.tan_inter[0] = tan
    lAnimCurve = pNode.LclScaling.GetCurve(pAnimLayer, "Y")
    if lAnimCurve:
        #print("        SY")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.scale, "Y")
        duration = max(duration, dur)
        bone_anim.tan_inter[1] = tan
    lAnimCurve = pNode.LclScaling.GetCurve(pAnimLayer, "Z")
    if lAnimCurve:
        #print("        SZ")
        (dur, ang, tan) = DisplayCurve(lAnimCurve, bone_anim.scale, "Z")
        duration = max(duration, dur)
        bone_anim.tan_inter[2] = tan
    #print(bone_anim.tan_inter)
    return (bone_anim, (duration, anglescale) )
def DisplayCurve(pCurve, array, axis):
    # a curve are the frames
    from animations.general_animation import AnimComponent
    #interpolation = [ "?", "constant", "linear", "cubic"]

    lKeyCount = pCurve.KeyGetCount()

    tan_inter = 0

    for lCount in range(lKeyCount):
        lKeyValue = pCurve.KeyGetValue(lCount)
        lKeyTime  = pCurve.KeyGetTime(lCount).GetFrameCount()
        lKeyTan = InterpolationFlagToIndex(pCurve.KeyGetInterpolation(lCount))
        anim_comp = AnimComponent(lKeyTime, lKeyValue, 0, 0, lKeyTan)
        #anim_comp.tan_inter = max( lKeyTan - 2, 0)
        tan_inter = max(tan_inter, lKeyTan - 2)
        #print(axis, lKeyValue, lKeyTime, lKeyTan)
        array[axis].append(anim_comp)
    #print(tan_inter)
    return (array[axis][-1].time, array[axis][-1].value, tan_inter)


def InterpolationFlagToIndex(flags):
	if (flags&KFCURVE_INTERPOLATION_CONSTANT)==KFCURVE_INTERPOLATION_CONSTANT:
	   return 1
	if (flags&KFCURVE_INTERPOLATION_LINEAR)==KFCURVE_INTERPOLATION_LINEAR:
	   return 2
	if (flags&KFCURVE_INTERPOLATION_CUBIC)==KFCURVE_INTERPOLATION_CUBIC:
	   return 3
	return 0

#lcl translation is the thing we want to capture as defaults 66 to 68 type: model
def DisplayNodeHierarchy(pNode, base_pose):
    print(pNode.GetName() )
    this_bone = []

    #process pnode properties
    #lcltranslation
    property = pNode.FindProperty("Lcl Scaling", False)
    property = fbx.FbxPropertyDouble3(property)
    lDefault = property.Get()
    
    this_bone.append( (lDefault[0], lDefault[1], lDefault[2]) ) 
    property = pNode.FindProperty("Lcl Rotation", False)
    property = fbx.FbxPropertyDouble3(property)
    lDefault = property.Get()
    
    this_bone.append( (lDefault[0], lDefault[1], lDefault[2]) ) 
    property = pNode.FindProperty("Lcl Translation", False)
    property = fbx.FbxPropertyDouble3(property)
    lDefault = property.Get()
    this_bone.append( (lDefault[0], lDefault[1], lDefault[2]) ) 
    
    base_pose.append(this_bone)

    for i in range( pNode.GetChildCount() ):
        DisplayNodeHierarchy(pNode.GetChild(i),base_pose)

def DisplayRootNode(pNode, base_pose):
    print(pNode.GetName() )
    this_bone = []

    #process pnode properties
    #lcltranslation
    property = pNode.FindProperty("Lcl Scaling", False)
    property = fbx.FbxPropertyDouble3(property)
    lDefault = property.Get()
    
    this_bone.append( (lDefault[0], lDefault[1], lDefault[2]) ) 
    property = pNode.FindProperty("Lcl Rotation", False)
    property = fbx.FbxPropertyDouble3(property)
    lDefault = property.Get()
    
    this_bone.append( (lDefault[0], lDefault[1], lDefault[2]) ) 
    property = pNode.FindProperty("Lcl Translation", False)
    property = fbx.FbxPropertyDouble3(property)
    lDefault = property.Get()
    this_bone.append( (lDefault[0], lDefault[1], lDefault[2]) ) 
    
    base_pose.append(this_bone)