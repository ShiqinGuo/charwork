from volcengine.visual.VisualService import VisualService
import os

visual_service = VisualService()
visual_service.set_ak(os.getenv('VOLCENGINE_ACCESS_KEY_ID'))
visual_service.set_sk(os.getenv('VOLCENGINE_SECRET_ACCESS_KEY'))

resp = visual_service.ocr_normal({
    "image_url": "http://psbet1y7ve.veimagex-pub.cn-north-1.volces.com/tos-cn-i-psbet1y7ve/c50736c8e54b4a0f996839137e4a7228.jpg~tplv-psbet1y7ve-image.image?sign=1772264440-rand-imagex-64f9d7b23fee206aecbe62b17209aa7b"
})

print(resp)
