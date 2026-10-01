from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Service, Order
from .serializers import ServiceSerializer, OrderSerializer
from .permissions import IsAuthorOrReadOnly

# Create your views here.

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    # Настройки фильтрации, поиска и сортировки
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['title', 'description']
    ordering_fields = ['base_price', 'created_at']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
        cache.delete('top_5_services')  # Сброс кэша при добавлении

    def perform_update(self, serializer):
        serializer.save()
        cache.delete('top_5_services')  # Сброс кэша при обновлении

    def perform_destroy(self, instance):
        instance.delete()
        cache.delete('top_5_services')  # Сброс кэша при удалении

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def top(self, request):
        """Эндпоинт Топ-5 популярных/новых услуг с кэшированием"""
        cached_top = cache.get('top_5_services')
        if cached_top is not None:
            return Response(cached_top)

        # Выбираем 5 свежих активных услуг
        top_services = Service.objects.filter(is_active=True).order_by('-created_at')[:5]
        serializer = self.get_serializer(top_services, many=True)
        data = serializer.data

        # Сохраняем в кэш на 1 час
        cache.set('top_5_services', data, 3600)
        return Response(data)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer

    def get_permissions(self):
        # Оставить заявку может любой клиент
        if self.action == 'create':
            return [permissions.AllowAny()]
        # Удалять заявки может только Администратор
        if self.action in ['destroy']:
            return [permissions.IsAdminUser()]
        # Просматривать заявки могут только авторизованные мастера
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all()
        if user.is_authenticated:
            # Мастер видит ТОЛЬКО заявки, оставленные на ЕГО услуги
            return Order.objects.filter(service__author=user)
        return Order.objects.none()