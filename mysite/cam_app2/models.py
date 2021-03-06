from django.db import models
from django.shortcuts import render
from django.conf import settings
from django import forms

from modelcluster.fields import ParentalKey

from wagtail.admin.edit_handlers import (
    FieldPanel,
    MultiFieldPanel,
    InlinePanel,
    StreamFieldPanel,
    PageChooserPanel,
)
from wagtail.core.models import Page, Orderable
from wagtail.core.fields import RichTextField, StreamField
from wagtail.images.edit_handlers import ImageChooserPanel
from django.core.files.storage import default_storage

from pathlib import Path

from streams import blocks

import sqlite3, datetime, os, uuid, glob, cv2
from matplotlib import pyplot as plt
from tensorflow import keras
import numpy as np
from PIL import Image

str_uuid = uuid.uuid4()  # The UUID for image uploading

# CREATE INFERENCE FUNCTION HERE
#func (img)
#process img usinfg model
#get mask
#img2=img+mask
#return img2

# =========CUSTOM CODE BELOW=========
model_unet = keras.models.load_model(f'{settings.MEDIA_ROOT}/model/1000epochs_unet.h5', compile=False)

def inference(model):
 arr = []
 for ind, i in enumerate(glob.glob(f'{settings.MEDIA_ROOT}/uploadedPics/*.jpg')):
    #=====1. Read the Image=====
    img = cv2.imread(i, cv2.IMREAD_COLOR)
    img = cv2.resize(img, (224,224))
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    #=====2. Extract original image and image for model processing=====
    test_img_normal = img[:,:,:] #(224,224)
    test_img_input = np.expand_dims(img, 0) #(1, 224,224,1)
    #plt.imshow(test_img_normal)
    #plt.show()
    
    #=====3. Get predicted mask & save as img=====
    prediction_img = (model.predict(test_img_input)[0,:,:,0] > 0.2).astype(np.uint8) #(1,224,224,3)
    plt.imsave(f'{settings.MEDIA_ROOT}/Result/result{ind}.jpg', prediction_img, cmap='gray') 
    
    #=====4. Get mask overlapped on original image & save as img=====
    mask = Image.open(f'{settings.MEDIA_ROOT}/Result/result{ind}.jpg').convert('RGB') # Import & convert mask from binary to RGB
    overlay = cv2.addWeighted(np.array(test_img_normal),0.8,np.array(mask),1,0)  
    plt.imsave(f'{settings.MEDIA_ROOT}/Overlay/overlay{ind}.jpg', overlay, cmap='gray') 
    
    #=====5. Append overlapped image to array to call in serve()=====
    arr.append(f"{settings.MEDIA_URL}Overlay/overlay{ind}.jpg")

    #=====Old Testing Code=====
    #weee = cv2.imread(prediction_img, cv2.IMREAD_GRAYSCALE)
    #cv2.imshow('hi', weee)
    #cv2.waitKey(0)
    #prediction1 = np.expand_dims(prediction_img, 2) #saving in a fomrat that can be overlapped in cv2.addWeighted
    #print(np.shape(prediction_img))
    #print(np.shape(prediction1))
    #plt.imshow(prediction1, cmap='gray')
    #plt.show()
 return arr
# =====================================

def reset():
    files_result = glob.glob(str(Path(f'{settings.MEDIA_ROOT}/Result/*.*')), recursive=True)
    files_upload = glob.glob(str(Path(f'{settings.MEDIA_ROOT}/uploadedPics/*.*')), recursive=True)
    files = []
    if len(files_result) != 0:
        files.extend(files_result)
    if len(files_upload) != 0:
        files.extend(files_upload)
    if len(files) != 0:
        for f in files:
            try:
                if (not (f.endswith(".txt"))):
                    os.remove(f)
            except OSError as e:
                print("Error: %s : %s" % (f, e.strerror))
        file_li = [Path(f'{settings.MEDIA_ROOT}/Result/Result.txt'),
                   Path(f'{settings.MEDIA_ROOT}/uploadedPics/img_list.txt'),
                   Path(f'{settings.MEDIA_ROOT}/Result/stats.txt')]
        for p in file_li:
            file = open(Path(p), "r+")
            file.truncate(0)
            file.close()

# Create your models here.
class ImagePage(Page):
    """Image Page."""

    template = "cam_app2/image.html"

    max_count = 2

    name_title = models.CharField(max_length=100, blank=True, null=True)
    name_subtitle = RichTextField(features=["bold", "italic"], blank=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("name_title"),
                FieldPanel("name_subtitle"),

            ],
            heading="Page Options",
        ),
    ]

    def reset_context(self, request):
        context = super().get_context(request)
        context["my_uploaded_file_names"]= []
        context["my_result_file_names"]=[]
        context["my_staticSet_names"]= []
        context["my_lines"] = []
        return context

    def serve(self, request):
        context = self.reset_context(request)
        #reset()
        emptyButtonFlag = False
        if request.POST.get('start')=="":
            print(request.POST.get('start'))
            print("Start selected")
            output_arr = inference(model_unet)
            
            context["my_result_file_names"] = output_arr
            context["my_uploaded_file_names"] = open(Path(f'{settings.MEDIA_ROOT}/uploadedPics/img_list.txt'), 'r').readlines()
            return render(request, "cam_app2/image.html", context)

        if (request.FILES and emptyButtonFlag == False):
            print("reached here files")
            reset()
            self.reset_context(request)
            context["my_uploaded_file_names"] = []
            for file_obj in request.FILES.getlist("file_data"):
                #uuidStr = uuid.uuid4()
                #filename = f"{file_obj.name.split('.')[0]}_{uuidStr}.{file_obj.name.split('.')[-1]}"
                filename = f"{file_obj.name}"
                with default_storage.open(Path(f"uploadedPics/{filename}"), 'wb+') as destination:
                    for chunk in file_obj.chunks():
                        destination.write(chunk)
                #filename = Path(f"{settings.MEDIA_URL}uploadedPics/{file_obj.name.split('.')[0]}_{uuidStr}.{file_obj.name.split('.')[-1]}")
                filename = Path(f"{settings.MEDIA_URL}uploadedPics/{file_obj.name}")
                with open(Path(f'{settings.MEDIA_ROOT}/uploadedPics/img_list.txt'), 'a') as f:
                    f.write(str(filename))
                    f.write("\n")

                context["my_uploaded_file_names"].append(str(f'{str(filename)}'))
            return render(request, "cam_app2/image.html", context)

        return render(request, "cam_app2/image.html", {'page': self})
