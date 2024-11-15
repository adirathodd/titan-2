from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from .serializers import RegisterSerializer, LoginSerializer, StockSerializer
from .utils import send_verification_email
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Profile, Stock
import yfinance as yf
from django.db.models import Q

# Registration View
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user, request)
        return Response({"message": "User registered successfully. Please check your email to verify your account."}, status=status.HTTP_201_CREATED)

# Login View
class LoginView(APIView):
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.profile.is_email_verified:
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Email is not verified.'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

# Email Verification View
class VerifyEmail(APIView):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            # Ensure the user has a profile
            profile, created = Profile.objects.get_or_create(user=user)
            profile.is_email_verified = True
            profile.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token

            # Return tokens to frontend
            return Response({
                'message': 'Email verified successfully.',
                'refresh': str(refresh),
                'access': str(access),
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid verification link.'}, status=status.HTTP_400_BAD_REQUEST)

class StockSummary(APIView):
    def get(self, request, ticker):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if 'currentPrice' not in info or info['currentPrice'] is None:
                return Response(
                    {"valid": False, "message": "Invalid ticker symbol."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            stock_data = {
                "valid": True,
                "companyName": info.get("longName") or info.get("shortName"),
                "ticker": ticker.upper(),
                "currentPrice": info.get("currentPrice"),
                "marketCap": info.get("marketCap"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "exchange": info.get("exchange"),
            }
            
            time_periods = {
                "1d": "1d",
                "5d": "5d",
                "1mo": "1mo",
                "3mo": "3mo",
                "6mo": "6mo",
                "1y": "1y",
                "2y": "2y",
                "5y": "5y",
                "10y": "10y",
                "ytd": "ytd",
                "max": "max"
            }
            
            period = request.GET.get('period', '1mo')
            if period not in time_periods:
                return Response(
                    {"valid": False, "message": "Invalid time period specified."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hist = stock.history(period=time_periods[period])
            if hist.empty:
                return Response(
                    {"valid": False, "message": "No historical data available for this ticker."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            historical_data = {
                "dates": hist.index.strftime('%Y-%m-%d').tolist(),
                "open": hist['Open'].tolist(),
                "high": hist['High'].tolist(),
                "low": hist['Low'].tolist(),
                "close": hist['Close'].tolist(),
                "volume": hist['Volume'].tolist(),
            }
            
            response_data = {
                "stockDetails": stock_data,
                "historicalData": historical_data,
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            print(f"Error fetching stock data for ticker {ticker}: {e}")
            return Response(
                {"valid": False, "message": "An error occurred while fetching stock data."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TickerSuggestionsAPIView(APIView):
    def get(self, request, format=None):
        query = request.GET.get('query', '').strip().upper()
        if not query:
            return Response(
                {"error": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        stocks = Stock.objects.filter(
            Q(ticker__icontains=query) | Q(company_name__icontains=query)
        ).order_by('ticker')[:10]
        
        serializer = StockSerializer(stocks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)