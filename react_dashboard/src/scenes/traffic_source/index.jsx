import { Box } from '@mui/material'
import Header from '../../components/Header'
import TrafficSourceChart from '../../components/TrafficSource'

const TrafficSource = () => {
  return (
    <Box m="20px">
      <Header title="Traffic Source" subtitle="Analyze viewer discovery and discovery methods" />
      <TrafficSourceChart />
    </Box>
  );
};

export default TrafficSource;
