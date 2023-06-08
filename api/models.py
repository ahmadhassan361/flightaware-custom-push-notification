from django.db import models

# Create your models here.
class Callback(models.Model):
    data = models.TextField()

class StoreTrack(models.Model):
    flight_id = models.CharField(max_length=244,null=True,blank=True)
    token = models.CharField(max_length=244,null=True,blank=True)
    