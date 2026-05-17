from rest_framework import serializers


class OptionSerializer(serializers.Serializer):
    value = serializers.IntegerField(source="id")
    label = serializers.CharField(source="nombre")
